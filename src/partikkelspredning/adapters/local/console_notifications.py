"""Local `NotificationService` that just logs.

Stands in for real email delivery during local development; see
`partikkelspredning.adapters.azure.email_notifications` for the production
path. Actual email delivery is deliberately out of scope for this
iteration (see the root README's scope limitations) - this is expected to
remain the default for anyone running locally even once a real Azure
notification adapter exists.
"""
from __future__ import annotations

import logging

from partikkelspredning.domain.jobs import SimulationJob

logger = logging.getLogger("partikkelspredning.notifications")


class ConsoleNotificationService:
    def notify_job_completed(self, job: SimulationJob, result_url: str) -> None:
        logger.info("Job %s completed for %s -> %s", job.job_id, job.user_email, result_url)

    def notify_job_failed(self, job: SimulationJob, error_message: str) -> None:
        logger.info("Job %s failed for %s: %s", job.job_id, job.user_email, error_message)
