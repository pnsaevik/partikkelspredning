"""Tests for `api/function_app.py`'s HTTP trigger functions.

Each `@app.route`-decorated function is a thin wrapper around a plain
`_verb_noun(req, ...)` function (see that module's docstring) - these tests
call those directly with a hand-built `func.HttpRequest`, so no Azure
Functions host or emulator is needed. Job storage is always Azure now (see
`partikkelspredning.composition.build_job_service`), so - mirroring
`tests/test_api.py` - these tests use a fakes-backed `JobService` (see
`tests/fakes.py`) rather than the real composition root; that end-to-end
coverage now lives solely in `tests/azure_integration/`.
"""
from __future__ import annotations

import json

import azure.functions as func
import pytest

from function_app import (
    _claim_job,
    _complete_job,
    _fail_job,
    _forms_metadata,
    _get_job,
    _health,
    _index,
    _submit_job,
)
from partikkelspredning.domain.forms import Form


def _request(method: str, url: str, *, json_body=None, route_params=None) -> func.HttpRequest:
    body = json.dumps(json_body).encode() if json_body is not None else b""
    return func.HttpRequest(
        method=method,
        url=url,
        headers={"Content-Type": "application/json"},
        params={},
        route_params=route_params or {},
        body=body,
    )


def _valid_payload():
    return {
        "user_email": "user@example.com",
        "parameters": {"resolution": 100, "duration": 1.5, "experiment": "demo"},
    }


def test_submit_job_returns_201_with_job_id(job_service):
    response = _submit_job(_request("POST", "/jobs", json_body=_valid_payload()), job_service)
    assert response.status_code == 201
    body = json.loads(response.get_body())
    assert body["status"] == "queued"
    assert "job_id" in body


def test_submit_job_accepts_arbitrary_parameters(job_service):
    """No predefined schema is enforced - any JSON object is accepted as-is;
    see the root README on why (the compute server decides runnability)."""
    payload = {"user_email": "user@example.com", "parameters": {"anything": "goes"}}
    response = _submit_job(_request("POST", "/jobs", json_body=payload), job_service)
    assert response.status_code == 201
    assert json.loads(response.get_body())["parameters"] == {"anything": "goes"}


def test_submit_job_rejects_invalid_email(job_service):
    payload = {"user_email": "not-an-email", "parameters": _valid_payload()["parameters"]}
    response = _submit_job(_request("POST", "/jobs", json_body=payload), job_service)
    assert response.status_code == 422


def test_submit_job_rejects_non_json_body(job_service):
    req = func.HttpRequest(
        method="POST", url="/jobs", headers={}, params={}, route_params={}, body=b"not json"
    )
    response = _submit_job(req, job_service)
    assert response.status_code == 400


def test_get_job_returns_submitted_job(job_service):
    job_id = json.loads(_submit_job(_request("POST", "/jobs", json_body=_valid_payload()), job_service).get_body())[
        "job_id"
    ]
    response = _get_job(_request("GET", f"/jobs/{job_id}", route_params={"job_id": job_id}), job_service)
    assert response.status_code == 200
    assert json.loads(response.get_body())["job_id"] == job_id


def test_get_unknown_job_returns_404(job_service):
    req = _request("GET", "/jobs/does-not-exist", route_params={"job_id": "does-not-exist"})
    response = _get_job(req, job_service)
    assert response.status_code == 404


def test_claim_returns_204_when_nothing_queued(job_service):
    response = _claim_job(_request("POST", "/jobs/claim", json_body={"worker_id": "worker-1"}), job_service)
    assert response.status_code == 204


def test_claim_then_complete_full_lifecycle(job_service):
    job_id = json.loads(_submit_job(_request("POST", "/jobs", json_body=_valid_payload()), job_service).get_body())[
        "job_id"
    ]

    claim_response = _claim_job(_request("POST", "/jobs/claim", json_body={"worker_id": "worker-1"}), job_service)
    assert claim_response.status_code == 200
    assert json.loads(claim_response.get_body())["job_id"] == job_id

    complete_req = _request(
        "POST",
        f"/jobs/{job_id}/complete",
        json_body={"worker_id": "worker-1", "result_reference": "out.nc"},
        route_params={"job_id": job_id},
    )
    complete_response = _complete_job(complete_req, job_service)
    assert complete_response.status_code == 200
    body = json.loads(complete_response.get_body())
    assert body["status"] == "completed"
    assert body["result_url"] is not None


def test_fail_after_claim(job_service):
    job_id = json.loads(_submit_job(_request("POST", "/jobs", json_body=_valid_payload()), job_service).get_body())[
        "job_id"
    ]
    _claim_job(_request("POST", "/jobs/claim", json_body={"worker_id": "worker-1"}), job_service)

    fail_req = _request(
        "POST",
        f"/jobs/{job_id}/fail",
        json_body={"worker_id": "worker-1", "error_message": "boom"},
        route_params={"job_id": job_id},
    )
    response = _fail_job(fail_req, job_service)
    assert response.status_code == 200
    assert json.loads(response.get_body())["status"] == "failed"


def test_complete_without_claiming_is_a_conflict(job_service):
    job_id = json.loads(_submit_job(_request("POST", "/jobs", json_body=_valid_payload()), job_service).get_body())[
        "job_id"
    ]
    complete_req = _request(
        "POST",
        f"/jobs/{job_id}/complete",
        json_body={"worker_id": "worker-1", "result_reference": "out.nc"},
        route_params={"job_id": job_id},
    )
    response = _complete_job(complete_req, job_service)
    assert response.status_code == 409


def test_health_returns_ok():
    response = _health(_request("GET", "/health"))
    assert response.status_code == 200
    assert json.loads(response.get_body()) == {"status": "ok"}


def test_index_returns_the_precomputed_html():
    response = _index(_request("GET", "/"), "<html>hello</html>")
    assert response.status_code == 200
    assert "text/html" in response.mimetype
    assert response.get_body().decode() == "<html>hello</html>"


def test_forms_metadata_returns_json_with_parameters_and_urls():
    forms = [Form(id="a", name="Form A", description="First form", parameters=[])]
    form_urls = {"a": "https://example.com/forms/a.html"}

    response = _forms_metadata(_request("GET", "/forms"), forms, form_urls)

    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body["forms"] == [
        {"id": "a", "name": "Form A", "description": "First form", "parameters": [], "url": "https://example.com/forms/a.html"}
    ]
