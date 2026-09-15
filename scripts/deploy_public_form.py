#!/usr/bin/env python
"""Deploy the public job-submission form to Azure Blob Storage.

Manual/scripted trigger for `services.public_form_service.deploy_public_form`
(see FEATURE_PLAN.md's "public_form" plan - there is deliberately no HTTP
endpoint for this in this iteration). Requires `PARTIKKEL_STORAGE_MODE=azure`
and `AZURE_STORAGE_CONNECTION_STRING` to be set; prints the deployed form's
public URL on success.

Usage:
    pip install -e ".[azure]"
    PARTIKKEL_STORAGE_MODE=azure AZURE_STORAGE_CONNECTION_STRING="..." \\
        python scripts/deploy_public_form.py
"""
from __future__ import annotations

from partikkelspredning.composition import build_form_store
from partikkelspredning.config import get_settings
from partikkelspredning.services.public_form_service import deploy_public_form


def main() -> None:
    settings = get_settings()
    form_store = build_form_store(settings)
    url = deploy_public_form(form_store, api_base_url=settings.api_base_url)
    print(url)


if __name__ == "__main__":
    main()
