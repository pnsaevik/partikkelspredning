"""Port: where job metadata/state is persisted.

An implementation only has to make jobs durable and retrievable by id; it is
not responsible for deciding *which* queued job to hand out next - that is
`JobQueue`'s job (see `partikkelspredning.ports.queue`). Splitting these two
concerns is what lets the Azure adapters map cleanly onto Table Storage
(records) + Storage Queue (work distribution) without either one leaking
into the other, and lets the local CSV adapter use one file for each.
"""
from __future__ import annotations

from typing import Optional, Protocol

from partikkelspredning.domain.jobs import SimulationJob


class JobRepository(Protocol):
    def create(self, job: SimulationJob) -> None:
        """Persist a brand-new job. `job.job_id` is assumed not to exist yet."""

    def get(self, job_id: str) -> Optional[SimulationJob]:
        """Return the job with this id, or None if it doesn't exist."""

    def update(self, job: SimulationJob) -> None:
        """Persist changes to an existing job (found by `job.job_id`)."""
