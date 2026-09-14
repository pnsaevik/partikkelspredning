from __future__ import annotations

import pytest

from partikkelspredning.domain.errors import (
    InvalidTransitionError,
    JobNotFoundError,
    JobOwnershipError,
)
from partikkelspredning.domain.jobs import JobStatus


def _submit(job_service):
    return job_service.submit_job(
        user_email="user@example.com",
        parameters={"resolution": 100, "duration": 1.5, "experiment": "demo"},
    )


def test_submit_job_creates_a_queued_job(job_service):
    job = _submit(job_service)
    assert job.status == JobStatus.QUEUED
    assert job_service.get_job(job.job_id) == job


def test_submit_job_accepts_arbitrary_parameters_unmodified(job_service):
    """No predefined schema is enforced here - whatever JSON object is
    submitted is stored as-is. See the root README on why: the compute
    server that eventually claims the job decides what's runnable."""
    job = job_service.submit_job(
        user_email="user@example.com",
        parameters={"anything": "goes", "nested": {"a": 1}, "list": [1, 2, 3]},
    )
    assert job.parameters == {"anything": "goes", "nested": {"a": 1}, "list": [1, 2, 3]}


def test_submit_job_accepts_empty_parameters(job_service):
    job = job_service.submit_job(user_email="user@example.com", parameters={})
    assert job.parameters == {}


def test_get_job_raises_for_unknown_id(job_service):
    with pytest.raises(JobNotFoundError):
        job_service.get_job("does-not-exist")


def test_claim_job_returns_none_when_queue_is_empty(job_service):
    assert job_service.claim_job(worker_id="worker-1") is None


def test_claim_job_marks_the_job_as_processing(job_service):
    submitted = _submit(job_service)
    claimed = job_service.claim_job(worker_id="worker-1")
    assert claimed.job_id == submitted.job_id
    assert claimed.status == JobStatus.PROCESSING
    assert claimed.worker_id == "worker-1"
    assert claimed.claimed_at is not None


def test_claim_job_prevents_duplicate_claims(job_service):
    _submit(job_service)
    first = job_service.claim_job(worker_id="worker-1")
    second = job_service.claim_job(worker_id="worker-2")
    assert first is not None
    assert second is None


def test_complete_job_transitions_and_notifies(job_service, notifier):
    submitted = _submit(job_service)
    job_service.claim_job(worker_id="worker-1")
    completed = job_service.complete_job(
        job_id=submitted.job_id, worker_id="worker-1", result_reference="out.nc"
    )
    assert completed.status == JobStatus.COMPLETED
    assert completed.result_reference == "out.nc"
    assert notifier.completed == [(submitted.job_id, f"fake://{submitted.job_id}/out.nc")]


def test_fail_job_transitions_and_notifies(job_service, notifier):
    submitted = _submit(job_service)
    job_service.claim_job(worker_id="worker-1")
    failed = job_service.fail_job(job_id=submitted.job_id, worker_id="worker-1", error_message="boom")
    assert failed.status == JobStatus.FAILED
    assert failed.error_message == "boom"
    assert notifier.failed == [(submitted.job_id, "boom")]


def test_cannot_complete_a_job_that_was_never_claimed(job_service):
    submitted = _submit(job_service)
    with pytest.raises(InvalidTransitionError):
        job_service.complete_job(job_id=submitted.job_id, worker_id="worker-1", result_reference="out.nc")


def test_cannot_complete_with_the_wrong_worker_id(job_service):
    submitted = _submit(job_service)
    job_service.claim_job(worker_id="worker-1")
    with pytest.raises(JobOwnershipError):
        job_service.complete_job(job_id=submitted.job_id, worker_id="someone-else", result_reference="out.nc")


def test_cannot_fail_an_already_completed_job(job_service):
    submitted = _submit(job_service)
    job_service.claim_job(worker_id="worker-1")
    job_service.complete_job(job_id=submitted.job_id, worker_id="worker-1", result_reference="out.nc")
    with pytest.raises(InvalidTransitionError):
        job_service.fail_job(job_id=submitted.job_id, worker_id="worker-1", error_message="too late")


def test_resolve_result_url_is_none_before_completion(job_service):
    submitted = _submit(job_service)
    assert job_service.resolve_result_url(submitted) is None
