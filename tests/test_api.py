"""A small number of FastAPI endpoint tests.

Job storage is always Azure now (see
`partikkelspredning.composition.build_job_service`), so these tests inject
a fakes-backed `JobService` (see `tests/fakes.py`/`conftest.py`) via
`create_app(job_service=...)` rather than exercising the real composition
root end to end - that coverage now lives solely in
`tests/azure_integration/` (excluded by default; requires real/emulated
Azure Storage). These tests exercise HTTP routing/schema behavior against
the same business logic `tests/test_job_service.py` already covers
directly. Forms-registry startup pre-rendering still uses a real
`LocalFormStore` (see `settings` in conftest.py), since that has no Azure
dependency.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from partikkelspredning.api.app import create_app


@pytest.fixture
def client(settings, job_service):
    app = create_app(settings=settings, job_service=job_service)
    return TestClient(app)


def _valid_payload():
    return {
        "user_email": "user@example.com",
        "parameters": {"resolution": 100, "duration": 1.5, "experiment": "demo"},
    }


def test_submit_job_returns_201_with_job_id(client):
    response = client.post("/jobs", json=_valid_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert "job_id" in body


def test_submit_job_accepts_arbitrary_parameters(client):
    """No predefined schema is enforced - any JSON object is accepted as-is;
    see the root README on why (the compute server decides runnability)."""
    response = client.post(
        "/jobs", json={"user_email": "user@example.com", "parameters": {"anything": "goes"}}
    )
    assert response.status_code == 201
    assert response.json()["parameters"] == {"anything": "goes"}


def test_submit_job_rejects_invalid_email(client):
    response = client.post("/jobs", json={"user_email": "not-an-email", **{"parameters": _valid_payload()["parameters"]}})
    assert response.status_code == 422


def test_get_job_returns_submitted_job(client):
    job_id = client.post("/jobs", json=_valid_payload()).json()["job_id"]
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["job_id"] == job_id


def test_get_unknown_job_returns_404(client):
    response = client.get("/jobs/does-not-exist")
    assert response.status_code == 404


def test_claim_returns_204_when_nothing_queued(client):
    response = client.post("/jobs/claim", json={"worker_id": "worker-1"})
    assert response.status_code == 204


def test_claim_then_complete_full_lifecycle(client):
    job_id = client.post("/jobs", json=_valid_payload()).json()["job_id"]

    claim_response = client.post("/jobs/claim", json={"worker_id": "worker-1"})
    assert claim_response.status_code == 200
    assert claim_response.json()["job_id"] == job_id

    complete_response = client.post(
        f"/jobs/{job_id}/complete",
        json={"worker_id": "worker-1", "result_reference": "out.nc"},
    )
    assert complete_response.status_code == 200
    body = complete_response.json()
    assert body["status"] == "completed"
    assert body["result_url"] is not None


def test_fail_after_claim(client):
    job_id = client.post("/jobs", json=_valid_payload()).json()["job_id"]
    client.post("/jobs/claim", json={"worker_id": "worker-1"})

    response = client.post(f"/jobs/{job_id}/fail", json={"worker_id": "worker-1", "error_message": "boom"})
    assert response.status_code == 200
    assert response.json()["status"] == "failed"


def test_complete_without_claiming_is_a_conflict(client):
    job_id = client.post("/jobs", json=_valid_payload()).json()["job_id"]
    response = client.post(f"/jobs/{job_id}/complete", json={"worker_id": "worker-1", "result_reference": "out.nc"})
    assert response.status_code == 409


def test_generate_form_returns_html(client):
    response = client.post(
        "/form",
        json={"parameters": [{"name": "resolution", "type": "integer", "description": "Grid resolution"}]},
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'name="resolution"' in response.text
