"""Port: hands out queued work to compute workers, one job at a time.

`try_claim` must guarantee that, when multiple callers race to claim work
concurrently, each queued job id is handed to at most one of them - that is
the safety property `JobService.claim_job` relies on to prevent two workers
from picking up the same job. *How* each adapter provides that guarantee (a
file lock for the local CSV adapter, Azure Storage Queue's built-in
visibility-timeout for the Azure adapter) is an implementation detail this
port deliberately hides.
"""
from __future__ import annotations

from typing import Optional, Protocol


class JobQueue(Protocol):
    def enqueue(self, job_id: str) -> None:
        """Make `job_id` available to be claimed."""

    def try_claim(self) -> Optional[str]:
        """Return the next available job id, or None if the queue is empty.

        Once a job id has been returned to a caller, it must not be
        returned to any other caller (see the module docstring).
        """
