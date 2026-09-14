"""FastAPI dependency providers.

Pulling the `JobService`/`Settings` off `request.app.state` (set once by
`partikkelspredning.api.app.create_app`) - rather than importing a global -
is what lets tests build a fresh app with its own settings/adapters and get
correct isolation for free, with no dependency-override boilerplate needed
for the common case.
"""
from __future__ import annotations

from fastapi import Request

from partikkelspredning.config import Settings
from partikkelspredning.services.job_service import JobService


def get_job_service(request: Request) -> JobService:
    return request.app.state.job_service


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings
