"""FastAPI application factory - the composition root's entry point.

Building the app is separated from the module-level `app = ...` object (see
`partikkelspredning.main`) so tests can call `create_app(settings=...)` with
whatever `Settings` they need, and `api/function_app.py` can host the exact
same app under Azure Functions.
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI

from partikkelspredning.api.routes_form import router as form_router
from partikkelspredning.api.routes_jobs import router as jobs_router
from partikkelspredning.composition import build_job_service
from partikkelspredning.config import Settings, get_settings


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Partikkelspredning job submission API",
        description=(
            "Accepts and tracks simulation jobs for a future compute server to "
            "claim, execute, and report back on. See the project README for the "
            "full architecture and job lifecycle."
        ),
    )
    app.state.settings = settings
    app.state.job_service = build_job_service(settings)
    app.include_router(jobs_router)
    app.include_router(form_router)
    return app
