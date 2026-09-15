"""Port: publishes a generated static HTML form somewhere publicly readable.

`partikkelspredning.services.public_form_service.deploy_public_form` hands a
rendered form (see `partikkelspredning.services.form_service`) to a
`FormStore` adapter, which is responsible for making it reachable by a
plain, unauthenticated `GET` - a local filesystem path during development,
a public-read Azure Blob Storage container in production (see
`partikkelspredning.adapters.azure.blob_form_store.BlobFormStore`).
"""
from __future__ import annotations

from typing import Protocol


class FormStore(Protocol):
    def upload_form_html(self, form_name: str, html_content: str) -> str:
        """Publish `html_content` as `form_name`; return its public URL."""
