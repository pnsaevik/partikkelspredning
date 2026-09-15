"""Azure Functions adapter.

This module (together with everything under
`partikkelspredning.adapters.azure`) is one of the only two places that
import Azure SDKs - the other being `partikkelspredning.adapters.azure`
itself. Each HTTP-triggered function below is a thin translation layer
between `azure.functions.HttpRequest`/`HttpResponse` and `JobService`/the
forms registry (the same services `partikkelspredning.api.routes_jobs`/
`routes_index` call for the FastAPI app `tests/test_api.py` exercises) - no
business logic lives here, and none of the request/response schemas or
domain error handling are duplicated: they're imported from
`partikkelspredning.api.schemas` and `partikkelspredning.domain.errors`.

Azure Functions is the only real hosting target for this application (see
FEATURE_PLAN.md's "multiple_forms" AC6) - the FastAPI app
(`partikkelspredning.api.app`) still exists, but only for
`tests/test_api.py` to exercise directly via `TestClient`.

New endpoints are added here as a new `@app.route(...)`-decorated function
(mirroring the equivalent FastAPI route in `partikkelspredning.api`), not by
changing how the app is hosted - there is no ASGI layer to keep in sync.

Each route delegates to a plain `_verb_noun(req, ...)` function that takes
its dependencies (a `JobService`, `Settings`, pre-rendered forms data, ...)
as arguments rather than reaching for module state directly, so those
functions can be unit-tested by calling them with a hand-built
`func.HttpRequest` and fakes - see `tests/test_function_app.py`.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type, TypeVar

import azure.functions as func
from pydantic import BaseModel, ValidationError

from partikkelspredning.api.schemas import (
    ClaimedJobResponse,
    ClaimJobRequest,
    CompleteJobRequest,
    FailJobRequest,
    JobResponse,
    SubmitJobRequest,
)
from partikkelspredning.api.security import require_worker_auth
from partikkelspredning.composition import build_forms_store, build_job_service
from partikkelspredning.config import Settings, get_settings
from partikkelspredning.domain.errors import (
    InvalidTransitionError,
    JobNotFoundError,
    JobOwnershipError,
)
from partikkelspredning.domain.forms import Form
from partikkelspredning.services.form_registry import load_forms
from partikkelspredning.services.form_renderer import prerender_and_store, render_index_html
from partikkelspredning.services.job_service import JobService

ModelT = TypeVar("ModelT", bound=BaseModel)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# --- process-wide dependencies -----------------------------------------
#
# Built lazily on first use and cached for the lifetime of the worker
# process ("startup" here means "first invocation of a warm worker", not
# literal process start - Azure Functions has no FastAPI-style startup
# hook) - `PARTIKKEL_STORAGE_MODE` and the rest of the environment don't
# change between invocations of a warm worker.

_settings: Optional[Settings] = None
_job_service: Optional[JobService] = None
_forms: Optional[List[Form]] = None
_form_urls: Optional[Dict[str, str]] = None
_index_html: Optional[str] = None


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


def _get_job_service() -> JobService:
    global _job_service
    if _job_service is None:
        _job_service = build_job_service(_get_settings())
    return _job_service


def _get_forms() -> List[Form]:
    global _forms
    if _forms is None:
        _forms = load_forms()
    return _forms


def _get_form_urls() -> Dict[str, str]:
    global _form_urls
    if _form_urls is None:
        forms_store = build_forms_store(_get_settings())
        _form_urls = prerender_and_store(_get_forms(), forms_store, api_base_url=_get_settings().api_base_url)
    return _form_urls


def _get_index_html() -> str:
    global _index_html
    if _index_html is None:
        _index_html = render_index_html(_get_forms(), _get_form_urls())
    return _index_html


# --- request/response helpers -------------------------------------------


class _BadRequest(Exception):
    """Carries the HTTP response to return for a malformed request body."""

    def __init__(self, response: func.HttpResponse) -> None:
        self.response = response


def _json_response(payload: Any, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(body=json.dumps(payload), status_code=status_code, mimetype="application/json")


def _error_response(status_code: int, detail: Any) -> func.HttpResponse:
    return _json_response({"detail": detail}, status_code)


def _parse_json_body(req: func.HttpRequest, model: Type[ModelT]) -> ModelT:
    """Parse and validate the request body as `model`, or raise
    `_BadRequest` with the HTTP response to return - a 400 for unparsable
    JSON, a 422 (mirroring FastAPI's default error shape) for a body that
    doesn't match `model`."""
    try:
        raw = req.get_json()
    except ValueError as exc:
        raise _BadRequest(_error_response(400, f"Request body must be valid JSON: {exc}")) from exc
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise _BadRequest(_error_response(422, json.loads(exc.json()))) from exc


# --- job endpoints --------------------------------------------------------
#
# Translates between HTTP and `JobService`/domain errors only - see the
# equivalent FastAPI routes in `partikkelspredning.api.routes_jobs` for the
# same logic.


def _submit_job(req: func.HttpRequest, job_service: JobService) -> func.HttpResponse:
    """Enqueue a new job. `parameters` is accepted as-is, an arbitrary JSON
    object with no predefined schema - see `JobService.submit_job`."""
    try:
        request = _parse_json_body(req, SubmitJobRequest)
    except _BadRequest as exc:
        return exc.response
    job = job_service.submit_job(user_email=request.user_email, parameters=request.parameters, metadata=request.metadata)
    return _json_response(JobResponse.from_domain(job).model_dump(mode="json"), status_code=201)


def _get_job(req: func.HttpRequest, job_service: JobService) -> func.HttpResponse:
    """Look up a job's current state. An unrecognized `job_id` is just a 404 -
    it is never trusted to mean anything else."""
    job_id = req.route_params["job_id"]
    try:
        job = job_service.get_job(job_id)
    except JobNotFoundError as exc:
        return _error_response(404, str(exc))
    response = JobResponse.from_domain(job, result_url=job_service.resolve_result_url(job))
    return _json_response(response.model_dump(mode="json"))


def _claim_job(req: func.HttpRequest, job_service: JobService) -> func.HttpResponse:
    """For the future compute server: atomically claim one queued job.

    Returns 204 with no body if nothing is queued. See `require_worker_auth`
    for where authentication for this endpoint should be added.
    """
    require_worker_auth()
    try:
        request = _parse_json_body(req, ClaimJobRequest)
    except _BadRequest as exc:
        return exc.response
    job = job_service.claim_job(worker_id=request.worker_id)
    if job is None:
        return func.HttpResponse(status_code=204)
    response = ClaimedJobResponse(job_id=job.job_id, parameters=job.parameters, user_email=job.user_email, metadata=job.metadata)
    return _json_response(response.model_dump(mode="json"))


def _complete_job(req: func.HttpRequest, job_service: JobService) -> func.HttpResponse:
    """For the future compute server: report that a claimed job completed successfully."""
    require_worker_auth()
    job_id = req.route_params["job_id"]
    try:
        request = _parse_json_body(req, CompleteJobRequest)
    except _BadRequest as exc:
        return exc.response
    try:
        job = job_service.complete_job(job_id=job_id, worker_id=request.worker_id, result_reference=request.result_reference)
    except JobNotFoundError as exc:
        return _error_response(404, str(exc))
    except (InvalidTransitionError, JobOwnershipError) as exc:
        return _error_response(409, str(exc))
    response = JobResponse.from_domain(job, result_url=job_service.resolve_result_url(job))
    return _json_response(response.model_dump(mode="json"))


def _fail_job(req: func.HttpRequest, job_service: JobService) -> func.HttpResponse:
    """For the future compute server: report that a claimed job failed."""
    require_worker_auth()
    job_id = req.route_params["job_id"]
    try:
        request = _parse_json_body(req, FailJobRequest)
    except _BadRequest as exc:
        return exc.response
    try:
        job = job_service.fail_job(job_id=job_id, worker_id=request.worker_id, error_message=request.error_message)
    except JobNotFoundError as exc:
        return _error_response(404, str(exc))
    except (InvalidTransitionError, JobOwnershipError) as exc:
        return _error_response(409, str(exc))
    return _json_response(JobResponse.from_domain(job).model_dump(mode="json"))


def _health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness check - used by the deploy workflow's smoke test to confirm
    the Function App is actually serving requests (not just that the deploy
    step itself reported success)."""
    return _json_response({"status": "ok"})


def _index(req: func.HttpRequest, index_html: str) -> func.HttpResponse:
    """Landing page linking to every pre-rendered form - see
    `partikkelspredning.api.routes_index`'s equivalent FastAPI route."""
    return func.HttpResponse(body=index_html, status_code=200, mimetype="text/html")


def _forms_metadata(req: func.HttpRequest, forms: List[Form], form_urls: Dict[str, str]) -> func.HttpResponse:
    """Forms registry metadata for programmatic access - see
    `partikkelspredning.api.routes_index`'s equivalent FastAPI route."""
    payload = {
        "forms": [
            {
                "id": form.id,
                "name": form.name,
                "description": form.description,
                "parameters": [p.model_dump(mode="json") for p in form.parameters],
                "url": form_urls[form.id],
            }
            for form in forms
        ]
    }
    return _json_response(payload)


# --- Azure Functions triggers ---------------------------------------------


@app.route(route="jobs", methods=["POST"])
def submit_job(req: func.HttpRequest) -> func.HttpResponse:
    return _submit_job(req, _get_job_service())


@app.route(route="jobs/{job_id}", methods=["GET"])
def get_job(req: func.HttpRequest) -> func.HttpResponse:
    return _get_job(req, _get_job_service())


@app.route(route="jobs/claim", methods=["POST"])
def claim_job(req: func.HttpRequest) -> func.HttpResponse:
    return _claim_job(req, _get_job_service())


@app.route(route="jobs/{job_id}/complete", methods=["POST"])
def complete_job(req: func.HttpRequest) -> func.HttpResponse:
    return _complete_job(req, _get_job_service())


@app.route(route="jobs/{job_id}/fail", methods=["POST"])
def fail_job(req: func.HttpRequest) -> func.HttpResponse:
    return _fail_job(req, _get_job_service())


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    return _health(req)


@app.route(route="", methods=["GET"])
def index(req: func.HttpRequest) -> func.HttpResponse:
    return _index(req, _get_index_html())


@app.route(route="forms", methods=["GET"])
def forms_metadata(req: func.HttpRequest) -> func.HttpResponse:
    return _forms_metadata(req, _get_forms(), _get_form_urls())
