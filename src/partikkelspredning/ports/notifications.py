"""Port: tells a user their job finished (or failed).

Kept independent of any specific delivery mechanism (email, SMS, a queue
another system reads, ...) - business logic only needs to know that a
notification *can* be sent, never how.
"""
from __future__ import annotations

from typing import Protocol

from partikkelspredning.domain.jobs import SimulationJob


class NotificationService(Protocol):
    def notify_job_completed(self, job: SimulationJob, result_url: str) -> None: ...

    def notify_job_failed(self, job: SimulationJob, error_message: str) -> None: ...
