"""Deploys the one hardcoded public job-submission form to a `FormStore`.

This is a manually/scripted deployment step (see `scripts/deploy_public_form.py`
at the repo root), not an HTTP endpoint - `POST /form` remains a general
render-any-parameter-set convenience, unrelated to this fixed form. Reuses
`form_service.generate_form_html` for the HTML itself; the field set comes
from `domain.public_forms.PUBLIC_FORM_PARAMETERS`.
"""
from __future__ import annotations

from partikkelspredning.domain.public_forms import PUBLIC_FORM_NAME, PUBLIC_FORM_PARAMETERS
from partikkelspredning.ports.form_store import FormStore
from partikkelspredning.services.form_service import generate_form_html


def deploy_public_form(form_store: FormStore, *, api_base_url: str) -> str:
    """Render the public form and upload it via `form_store`; return its public URL."""
    html = generate_form_html(
        PUBLIC_FORM_PARAMETERS,
        api_base_url=api_base_url,
        title="Submit a simulation job",
    )
    return form_store.upload_form_html(PUBLIC_FORM_NAME, html)
