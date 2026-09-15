"""HTTP route for generating the static submission form."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from partikkelspredning.api.dependencies import get_settings_dep
from partikkelspredning.api.schemas import FormRequest
from partikkelspredning.config import Settings
from partikkelspredning.services.form_renderer import generate_form_html

router = APIRouter(tags=["form"])


@router.post("/form", response_class=HTMLResponse)
def generate_form(request: FormRequest, settings: Settings = Depends(get_settings_dep)) -> HTMLResponse:
    """Render a standalone HTML form for the given parameter definitions.

    The generated page POSTs to this deployment's `/jobs` endpoint (using
    the configured `PARTIKKEL_API_BASE_URL`) and works as a saved,
    standalone HTML file.
    """
    html = generate_form_html(request.parameters, api_base_url=settings.api_base_url, title=request.title)
    return HTMLResponse(content=html)
