"""Azure Blob Storage implementation of `ResultStore`.

Returns the blob's URL directly. A real deployment should front this with a
short-lived SAS token or a private container behind an authenticated
download endpoint rather than relying on a bare public URL - see the root
README's Security section.
"""
from __future__ import annotations

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient


class BlobResultStore:
    def __init__(self, connection_string: str, container_name: str = "results") -> None:
        self._service = BlobServiceClient.from_connection_string(connection_string)
        self._container_name = container_name
        try:
            self._service.create_container(container_name)
        except ResourceExistsError:
            pass

    def build_result_url(self, job_id: str, result_reference: str) -> str:
        blob_client = self._service.get_blob_client(self._container_name, result_reference)
        return blob_client.url
