"""Azure Functions adapter.

This module (together with everything under
`partikkelspredning.adapters.azure`) is one of the only two places that
import Azure SDKs - the other being `partikkelspredning.adapters.azure`
itself. Each HTTP-triggered function below is a thin translation layer
between `azure.functions.HttpRequest`/`HttpResponse` and `JobService` (the
same service `partikkelspredning.api.routes_jobs`/`routes_form` call for
local, uvicorn-hosted development) - no business logic lives here, and none
of the request/response schemas or domain error handling are duplicated:
they're imported from `partikkelspredning.api.schemas` and
`partikkelspredning.domain.errors`.

    local:  browser -> uvicorn -> FastAPI app (partikkelspredning.main:app)
    Azure:  browser -> Azure Functions -> the functions below, calling
                                           straight into JobService

New endpoints are added here as a new `@app.route(...)`-decorated function
(mirroring the equivalent FastAPI route in `partikkelspredning.api`), not by
changing how the app is hosted - there is no ASGI layer to keep in sync.

Each route delegates to a plain `_verb_noun(req, ...)` function that takes
its dependencies (a `JobService`, `Settings`, ...) as arguments rather than
reaching for module state directly, so those functions can be unit-tested
by calling them with a hand-built `func.HttpRequest` and a `JobService`
wired to fakes or a tmp-dir-backed local deployment - see
`tests/test_function_app.py`.
"""
from __future__ import annotations

import json
from typing import Any, Optional, Type, TypeVar

import azure.functions as func
from pydantic import BaseModel, ValidationError

from partikkelspredning.api.schemas import (
    ClaimedJobResponse,
    ClaimJobRequest,
    CompleteJobRequest,
    FailJobRequest,
    FormRequest,
    JobResponse,
    SubmitJobRequest,
)
from partikkelspredning.api.security import require_worker_auth
from partikkelspredning.composition import build_job_service
from partikkelspredning.config import Settings, get_settings
from partikkelspredning.domain.errors import (
    InvalidTransitionError,
    JobNotFoundError,
    JobOwnershipError,
)
from partikkelspredning.services.form_service import generate_form_html
from partikkelspredning.services.job_service import JobService

ModelT = TypeVar("ModelT", bound=BaseModel)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# --- process-wide dependencies -----------------------------------------
#
# Built lazily on first use and cached for the lifetime of the worker
# process, the same way `partikkelspredning.main` builds its FastAPI `app`
# once at import time - `PARTIKKEL_STORAGE_MODE` and the rest of the
# environment don't change between invocations of a warm worker.

_settings: Optional[Settings] = None
_job_service: Optional[JobService] = None


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


def _generate_form(req: func.HttpRequest, settings: Settings) -> func.HttpResponse:
    """Render a standalone HTML form for the given parameter definitions.

    The generated page POSTs to this deployment's `/jobs` endpoint (using
    the configured `PARTIKKEL_API_BASE_URL`) and works as a saved,
    standalone HTML file.
    """
    try:
        request = _parse_json_body(req, FormRequest)
    except _BadRequest as exc:
        return exc.response
    html = generate_form_html(request.parameters, api_base_url=settings.api_base_url, title=request.title)
    return func.HttpResponse(body=html, status_code=200, mimetype="text/html")


def _health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness check - used by the deploy workflow's smoke test to confirm
    the Function App is actually serving requests (not just that the deploy
    step itself reported success)."""
    return _json_response({"status": "ok"})


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


@app.route(route="form", methods=["POST"])
def generate_form(req: func.HttpRequest) -> func.HttpResponse:
    return _generate_form(req, _get_settings())


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    return _health(req)
