"""The simulation job domain model and its state machine.

A `SimulationJob` moves through a small, explicit set of states::

    queued -> processing -> completed
                          -> failed

`queued` and `processing` are the only states a job can move *out of*;
`completed` and `failed` are terminal. `transition_status` is the single
place that enforces this - nothing else in the codebase should assign to
`job.status` directly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from partikkelspredning.domain.errors import InvalidTransitionError, JobOwnershipError


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# The only allowed (current -> next) transitions. Anything not listed here
# is rejected by `transition_status`. Keeping this as one explicit table
# (rather than scattered `if` checks) is what makes the lifecycle easy to
# audit and to extend later.
ALLOWED_TRANSITIONS: Dict[JobStatus, FrozenSet[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.PROCESSING}),
    JobStatus.PROCESSING: frozenset({JobStatus.COMPLETED, JobStatus.FAILED}),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.FAILED: frozenset(),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SimulationJob(BaseModel):
    """A single submitted simulation job and its current state.

    `worker_id` and `claimed_at` are recorded when a job is claimed so that
    a future lease/timeout mechanism can decide a claim has gone stale (for
    example: "processing" for longer than N minutes with no completion) and
    return the job to the queue. That mechanism is intentionally *not*
    implemented yet (see the root README), but the fields it will need
    already exist so adding it later won't require a data migration.
    """

    job_id: str = Field(default_factory=lambda: uuid4().hex)
    status: JobStatus = JobStatus.QUEUED
    parameters: Dict[str, Any] = Field(default_factory=dict)
    user_email: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    worker_id: Optional[str] = None
    claimed_at: Optional[datetime] = None

    result_reference: Optional[str] = None
    error_message: Optional[str] = None

    def transition_status(self, target: JobStatus, **fields: Any) -> None:
        """Move to `target`, or raise `InvalidTransitionError`.

        `fields` are additional attributes to set atomically with the
        transition (e.g. `worker_id=...` when moving to `processing`).
        """
        allowed = ALLOWED_TRANSITIONS.get(self.status, frozenset())
        if target not in allowed:
            raise InvalidTransitionError(self.status, target)
        for key, value in fields.items():
            setattr(self, key, value)
        self.status = target
        self.updated_at = utcnow()

    def ensure_claimed_by(self, worker_id: str) -> None:
        """Guard against a worker acting on a job it did not claim.

        See `JobOwnershipError` for why this is a correctness check, not a
        security boundary.
        """
        if self.worker_id is not None and self.worker_id != worker_id:
            raise JobOwnershipError(self.job_id, self.worker_id, worker_id)
