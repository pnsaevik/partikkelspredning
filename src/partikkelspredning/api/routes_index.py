"""HTTP routes for the forms registry landing page and metadata.

`GET /` returns the pre-rendered index page linking to every form; `GET
/forms` returns the same forms as JSON for programmatic access - both
built once at startup (see `api.app.create_app`'s startup handler) rather
than generated per-request (FEATURE_PLAN.md's "multiple_forms" AC3/AC4).
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter(tags=["forms"])


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return HTMLResponse(content=request.app.state.index_html)


@router.get("/forms")
def forms_metadata(request: Request) -> JSONResponse:
    forms = request.app.state.forms
    form_urls = request.app.state.form_urls
    return JSONResponse(
        content={
            "forms": [
                {
                    "id": form.id,
                    "name": form.name,
                    "description": form.description,
                    "parameters": [p.model_dump(mode="json") for p in form.parameters],
                    "url": form_urls[form.id],
                }
                for form in forms
            ]
        }
    )
