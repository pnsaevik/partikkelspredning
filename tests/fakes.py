"""In-memory fakes for the ports, used to unit-test `JobService` with no I/O.

Real adapters (CSV files, filesystem, Azure) are exercised separately in
`test_csv_adapters.py`; these fakes let the service-layer tests focus on
business logic and run fast.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from partikkelspredning.domain.jobs import SimulationJob


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: Dict[str, SimulationJob] = {}

    def create(self, job: SimulationJob) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> Optional[SimulationJob]:
        return self._jobs.get(job_id)

    def update(self, job: SimulationJob) -> None:
        self._jobs[job.job_id] = job


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._queue: List[str] = []

    def enqueue(self, job_id: str) -> None:
        self._queue.append(job_id)

    def try_claim(self) -> Optional[str]:
        if not self._queue:
            return None
        return self._queue.pop(0)


class FakeResultStore:
    def build_result_url(self, job_id: str, result_reference: str) -> str:
        return f"fake://{job_id}/{result_reference}"


class RecordingFormStore:
    def __init__(self) -> None:
        self.uploaded: Dict[str, str] = {}

    def upload_form_html(self, form_name: str, html_content: str) -> str:
        self.uploaded[form_name] = html_content
        return f"fake://forms/{form_name}.html"


class RecordingNotificationService:
    def __init__(self) -> None:
        self.completed: List[Tuple[str, str]] = []
        self.failed: List[Tuple[str, str]] = []

    def notify_job_completed(self, job: SimulationJob, result_url: str) -> None:
        self.completed.append((job.job_id, result_url))

    def notify_job_failed(self, job: SimulationJob, error_message: str) -> None:
        self.failed.append((job.job_id, error_message))
