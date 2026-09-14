"""Domain-level exceptions.

These are the only kinds of errors the domain and application-service layer
raise. The API layer (see `partikkelspredning.api.routes_jobs`) is
responsible for translating them into HTTP status codes; the domain itself
has no concept of HTTP.
"""
from __future__ import annotations

from typing import List


class DomainError(Exception):
    """Base class for all domain-level errors."""


class ParameterValidationError(DomainError):
    """Raised when submitted parameter values don't match their definition.

    `errors` lists every problem found (missing parameters, unknown
    parameters, wrong types, ...) rather than just the first one, so a
    caller can report everything that needs fixing in one pass.
    """

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class JobNotFoundError(DomainError):
    """Raised when a job ID does not refer to any known job."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"No job found with id {job_id!r}")


class InvalidTransitionError(DomainError):
    """Raised when a job status transition is not allowed.

    `current` and `target` are `JobStatus` values; typed as plain objects
    here to avoid a circular import with `partikkelspredning.domain.jobs`.
    """

    def __init__(self, current: object, target: object) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition job from {current!r} to {target!r}")


class JobOwnershipError(DomainError):
    """Raised when a worker tries to complete/fail a job it did not claim.

    This only catches bugs or misuse in a cooperative, single-tenant setup -
    it is not a security boundary. Real access control for compute-server
    endpoints is a documented follow-up; see the root README's Security
    section.
    """

    def __init__(self, job_id: str, expected_worker_id: str, actual_worker_id: str) -> None:
        self.job_id = job_id
        self.expected_worker_id = expected_worker_id
        self.actual_worker_id = actual_worker_id
        super().__init__(
            f"Job {job_id!r} was claimed by {expected_worker_id!r}, not {actual_worker_id!r}"
        )
