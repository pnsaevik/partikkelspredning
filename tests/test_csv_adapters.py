from __future__ import annotations

from partikkelspredning.adapters.local.csv_queue import CsvJobQueue
from partikkelspredning.adapters.local.csv_repository import CsvJobRepository
from partikkelspredning.domain.jobs import JobStatus, SimulationJob, utcnow


def test_csv_repository_round_trips_a_job(tmp_path):
    repo = CsvJobRepository(tmp_path / "jobs.csv")
    job = SimulationJob(user_email="user@example.com", parameters={"resolution": 100, "experiment": "x"})
    repo.create(job)

    fetched = repo.get(job.job_id)

    assert fetched is not None
    assert fetched.job_id == job.job_id
    assert fetched.status == JobStatus.QUEUED
    assert fetched.parameters == {"resolution": 100, "experiment": "x"}
    assert fetched.user_email == "user@example.com"
    assert fetched.worker_id is None
    assert fetched.claimed_at is None


def test_csv_repository_get_returns_none_for_unknown_id(tmp_path):
    repo = CsvJobRepository(tmp_path / "jobs.csv")
    assert repo.get("does-not-exist") is None


def test_csv_repository_update_persists_changes(tmp_path):
    repo = CsvJobRepository(tmp_path / "jobs.csv")
    job = SimulationJob(user_email="user@example.com", parameters={})
    repo.create(job)

    job.transition_status(JobStatus.PROCESSING, worker_id="worker-1", claimed_at=utcnow())
    repo.update(job)

    fetched = repo.get(job.job_id)
    assert fetched.status == JobStatus.PROCESSING
    assert fetched.worker_id == "worker-1"
    assert fetched.claimed_at is not None


def test_csv_repository_survives_reopening(tmp_path):
    csv_path = tmp_path / "jobs.csv"
    job = SimulationJob(user_email="user@example.com", parameters={})
    CsvJobRepository(csv_path).create(job)

    reopened = CsvJobRepository(csv_path)
    fetched = reopened.get(job.job_id)
    assert fetched is not None
    assert fetched.job_id == job.job_id


def test_csv_queue_is_fifo(tmp_path):
    queue = CsvJobQueue(tmp_path / "queue.txt")
    queue.enqueue("job-1")
    queue.enqueue("job-2")

    assert queue.try_claim() == "job-1"
    assert queue.try_claim() == "job-2"
    assert queue.try_claim() is None


def test_csv_queue_survives_reopening(tmp_path):
    queue_path = tmp_path / "queue.txt"
    CsvJobQueue(queue_path).enqueue("job-1")

    reopened = CsvJobQueue(queue_path)
    assert reopened.try_claim() == "job-1"
    assert reopened.try_claim() is None
