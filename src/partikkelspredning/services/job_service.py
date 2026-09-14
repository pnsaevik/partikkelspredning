"""Application service: orchestrates the job lifecycle.

This is where domain objects (`SimulationJob`, parameter validation) meet
the ports (`JobRepository`, `JobQueue`, `ResultStore`, `NotificationService`).
It knows *that* those capabilities exist and *how* to sequence them, but
nothing about which concrete adapter is plugged in - that's decided once, at
startup, by whatever builds a `JobService` (see
`partikkelspredning.composition.build_job_service`).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from partikkelspredning.domain.errors import JobNotFoundError
from partikkelspredning.domain.jobs import JobStatus, SimulationJob, utcnow
from partikkelspredning.domain.parameters import ParameterDefinition, validate_parameters
from partikkelspredning.ports.notifications import NotificationService
from partikkelspredning.ports.queue import JobQueue
from partikkelspredning.ports.repository import JobRepository
from partikkelspredning.ports.result_store import ResultStore


class JobService:
    def __init__(
        self,
        *,
        parameter_definitions: List[ParameterDefinition],
        repository: JobRepository,
        queue: JobQueue,
        result_store: ResultStore,
        notifier: NotificationService,
    ) -> None:
        self._parameter_definitions = parameter_definitions
        self._repository = repository
        self._queue = queue
        self._result_store = result_store
        self._notifier = notifier

    def submit_job(
        self,
        *,
        user_email: str,
        parameters: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SimulationJob:
        """Validate parameters and enqueue a new job.

        Raises `partikkelspredning.domain.errors.ParameterValidationError` if
        `parameters` doesn't match the configured parameter definitions.
        """
        validated = validate_parameters(self._parameter_definitions, parameters)
        job = SimulationJob(user_email=user_email, parameters=validated, metadata=metadata or {})
        self._repository.create(job)
        self._queue.enqueue(job.job_id)
        return job

    def get_job(self, job_id: str) -> SimulationJob:
        """Raises `JobNotFoundError` if `job_id` is unknown."""
        job = self._repository.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def resolve_result_url(self, job: SimulationJob) -> Optional[str]:
        """The job's result URL, or None if it has no result yet."""
        if job.result_reference is None:
            return None
        return self._result_store.build_result_url(job.job_id, job.result_reference)

    def claim_job(self, *, worker_id: str) -> Optional[SimulationJob]:
        """Atomically hand one queued job to a compute worker, or return None.

        Claiming is a two-step handshake by design: the `JobQueue` decides
        *which* job id becomes available next and guarantees it is handed to
        exactly one caller (see each adapter's docstring for how); the
        repository is then updated to record the resulting `processing`
        state. If the process crashes between the two steps, the job is
        dequeued but still shows as `queued` in the repository -
        reconciling that is part of the future lease/retry mechanism
        mentioned in the root README.
        """
        job_id = self._queue.try_claim()
        if job_id is None:
            return None
        job = self._repository.get(job_id)
        if job is None:  # pragma: no cover - defensive; indicates an adapter bug
            raise JobNotFoundError(job_id)
        job.transition_status(JobStatus.PROCESSING, worker_id=worker_id, claimed_at=utcnow())
        self._repository.update(job)
        return job

    def complete_job(self, *, job_id: str, worker_id: str, result_reference: str) -> SimulationJob:
        """Raises `JobNotFoundError`, `InvalidTransitionError`, or `JobOwnershipError`."""
        job = self.get_job(job_id)
        job.ensure_claimed_by(worker_id)
        job.transition_status(JobStatus.COMPLETED, result_reference=result_reference)
        self._repository.update(job)
        result_url = self.resolve_result_url(job)
        self._notifier.notify_job_completed(job, result_url)
        return job

    def fail_job(self, *, job_id: str, worker_id: str, error_message: str) -> SimulationJob:
        """Raises `JobNotFoundError`, `InvalidTransitionError`, or `JobOwnershipError`."""
        job = self.get_job(job_id)
        job.ensure_claimed_by(worker_id)
        job.transition_status(JobStatus.FAILED, error_message=error_message)
        self._repository.update(job)
        self._notifier.notify_job_failed(job, error_message)
        return job
