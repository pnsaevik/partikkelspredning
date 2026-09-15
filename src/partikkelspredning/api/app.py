"""FastAPI application factory.

Building the app is separated from a module-level `app = ...` object so
tests can call `create_app(settings=..., job_service=...)` with whatever
they need - in particular, `tests/test_api.py` injects a fakes-backed
`JobService` directly (job storage is always Azure now, see
`partikkelspredning.composition.build_job_service`, so building the real
one needs real credentials). This app has no local, uvicorn-hosted
deployment target any more (see FEATURE_PLAN.md's "multiple_forms" AC6) -
it exists for `tests/test_api.py` to exercise via `TestClient`. A deployed
Azure Function App runs its own HTTP-triggered functions instead
(`api/function_app.py`) rather than hosting this app object.
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI

from partikkelspredning.api.routes_form import router as form_router
from partikkelspredning.api.routes_index import router as index_router
from partikkelspredning.api.routes_jobs import router as jobs_router
from partikkelspredning.composition import build_forms_store, build_job_service
from partikkelspredning.config import Settings, get_settings
from partikkelspredning.services.form_registry import load_forms
from partikkelspredning.services.form_renderer import prerender_and_store, render_index_html
from partikkelspredning.services.job_service import JobService


def create_app(settings: Optional[Settings] = None, job_service: Optional[JobService] = None) -> FastAPI:
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
    app.state.job_service = job_service if job_service is not None else build_job_service(settings)
    app.include_router(jobs_router)
    app.include_router(form_router)
    app.include_router(index_router)

    @app.on_event("startup")
    def _prerender_forms() -> None:
        # Fail-fast by design (FEATURE_PLAN.md's "multiple_forms" startup
        # design decision): a malformed registry or unreachable form store
        # should stop the app from ever accepting requests, not surface as
        # a 500 on the first `GET /`.
        forms = load_forms()
        forms_store = build_forms_store(settings)
        form_urls = prerender_and_store(forms, forms_store, api_base_url=settings.api_base_url)
        app.state.forms = forms
        app.state.form_urls = form_urls
        app.state.index_html = render_index_html(forms, form_urls)

    return app
