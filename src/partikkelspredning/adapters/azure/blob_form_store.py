"""Azure Blob Storage implementation of `FormStore`.

Uploads generated form HTML into a container created with public
(anonymous) blob-level read access, so the page can be opened directly in a
browser with no authentication - see FEATURE_PLAN.md's "public_form"
acceptance criteria. Forms are static, non-secret convenience pages, so a
public container is an intentional choice here, unlike `BlobResultStore`'s
bare blob URL, which that module's docstring already flags as needing a SAS
token or an authenticated download endpoint in a real deployment.
"""
from __future__ import annotations

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient, ContentSettings, PublicAccess


class BlobFormStore:
    def __init__(self, connection_string: str, container_name: str = "forms") -> None:
        self._service = BlobServiceClient.from_connection_string(connection_string)
        self._container_name = container_name
        try:
            self._service.create_container(container_name, public_access=PublicAccess.BLOB)
        except ResourceExistsError:
            pass

    def upload_form_html(self, form_name: str, html_content: str) -> str:
        blob_client = self._service.get_blob_client(self._container_name, f"{form_name}.html")
        blob_client.upload_blob(
            html_content.encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type="text/html"),
        )
        return blob_client.url
