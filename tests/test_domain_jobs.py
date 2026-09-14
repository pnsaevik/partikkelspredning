from __future__ import annotations

import pytest

from partikkelspredning.domain.errors import InvalidTransitionError, JobOwnershipError
from partikkelspredning.domain.jobs import JobStatus, SimulationJob


def _new_job() -> SimulationJob:
    return SimulationJob(user_email="user@example.com", parameters={"a": 1})


def test_new_job_starts_queued():
    job = _new_job()
    assert job.status == JobStatus.QUEUED
    assert job.worker_id is None
    assert job.claimed_at is None


def test_queued_can_transition_to_processing():
    job = _new_job()
    job.transition_status(JobStatus.PROCESSING, worker_id="worker-1")
    assert job.status == JobStatus.PROCESSING
    assert job.worker_id == "worker-1"


def test_processing_can_transition_to_completed():
    job = _new_job()
    job.transition_status(JobStatus.PROCESSING, worker_id="worker-1")
    job.transition_status(JobStatus.COMPLETED, result_reference="out.nc")
    assert job.status == JobStatus.COMPLETED
    assert job.result_reference == "out.nc"


def test_processing_can_transition_to_failed():
    job = _new_job()
    job.transition_status(JobStatus.PROCESSING, worker_id="worker-1")
    job.transition_status(JobStatus.FAILED, error_message="boom")
    assert job.status == JobStatus.FAILED
    assert job.error_message == "boom"


def test_cannot_skip_processing():
    job = _new_job()
    with pytest.raises(InvalidTransitionError):
        job.transition_status(JobStatus.COMPLETED, result_reference="out.nc")


def test_terminal_states_have_no_further_transitions():
    job = _new_job()
    job.transition_status(JobStatus.PROCESSING, worker_id="worker-1")
    job.transition_status(JobStatus.COMPLETED, result_reference="out.nc")
    with pytest.raises(InvalidTransitionError):
        job.transition_status(JobStatus.FAILED, error_message="too late")


def test_ensure_claimed_by_passes_for_the_claiming_worker():
    job = _new_job()
    job.transition_status(JobStatus.PROCESSING, worker_id="worker-1")
    job.ensure_claimed_by("worker-1")  # does not raise


def test_ensure_claimed_by_rejects_a_different_worker():
    job = _new_job()
    job.transition_status(JobStatus.PROCESSING, worker_id="worker-1")
    with pytest.raises(JobOwnershipError):
        job.ensure_claimed_by("worker-2")


def test_ensure_claimed_by_passes_for_an_unclaimed_job():
    job = _new_job()
    job.ensure_claimed_by("anyone")  # no worker_id set yet - does not raise
