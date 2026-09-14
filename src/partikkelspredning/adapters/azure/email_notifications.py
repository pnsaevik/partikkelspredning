"""Azure notification adapter (email delivery not yet implemented).

Real email delivery is explicitly out of scope for this iteration (see the
root README's scope limitations) - only the *interface* needs to exist so a
real one (Azure Communication Services Email, SendGrid, ...) can be dropped
in later without touching `JobService`. For now this logs what would be
sent, using the same logging pipeline Azure Functions already captures via
Application Insights.
"""
from __future__ import annotations

import logging

from partikkelspredning.domain.jobs import SimulationJob

logger = logging.getLogger("partikkelspredning.notifications.azure")


class AzureEmailNotificationService:
    def notify_job_completed(self, job: SimulationJob, result_url: str) -> None:
        logger.info("Would email %s: job %s completed -> %s", job.user_email, job.job_id, result_url)

    def notify_job_failed(self, job: SimulationJob, error_message: str) -> None:
        logger.info("Would email %s: job %s failed: %s", job.user_email, job.job_id, error_message)
