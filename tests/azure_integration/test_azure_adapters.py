"""Optional integration tests against a real (or Azurite-emulated) Azure Storage account.

Excluded from the default `pytest` run - see the `azure_integration` marker
and `addopts` in pyproject.toml. Run explicitly with:

    pip install -e ".[azure]"
    AZURE_STORAGE_CONNECTION_STRING="..." pytest -m azure_integration

Skipped automatically if the azure-* packages aren't installed or the
connection string isn't set, so the default test suite never needs Azure
credentials.
"""
from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("azure.data.tables")
pytest.importorskip("azure.storage.queue")
pytest.importorskip("azure.storage.blob")

CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

pytestmark = [
    pytest.mark.azure_integration,
    pytest.mark.skipif(not CONNECTION_STRING, reason="AZURE_STORAGE_CONNECTION_STRING is not set"),
]


def test_table_repository_round_trip():
    from partikkelspredning.adapters.azure.table_repository import TableJobRepository
    from partikkelspredning.domain.jobs import SimulationJob

    repository = TableJobRepository(CONNECTION_STRING, table_name=f"testjobs{uuid.uuid4().hex[:8]}")
    job = SimulationJob(user_email="user@example.com", parameters={"a": 1})

    repository.create(job)
    fetched = repository.get(job.job_id)

    assert fetched is not None
    assert fetched.job_id == job.job_id
    assert fetched.parameters == {"a": 1}


def test_storage_queue_round_trip():
    from partikkelspredning.adapters.azure.storage_queue import StorageQueueJobQueue

    queue = StorageQueueJobQueue(CONNECTION_STRING, queue_name=f"testqueue{uuid.uuid4().hex[:8]}")

    queue.enqueue("job-123")
    claimed = queue.try_claim()

    assert claimed == "job-123"
    assert queue.try_claim() is None


def test_blob_form_store_round_trip():
    from azure.storage.blob import BlobClient

    from partikkelspredning.adapters.azure.blob_form_store import BlobFormStore

    form_store = BlobFormStore(CONNECTION_STRING, container_name=f"testforms{uuid.uuid4().hex[:8]}")

    url = form_store.upload_form_html("my-form", "<html><body>hi</body></html>")

    # No credential passed: proves the blob is readable by an anonymous
    # client, i.e. that the container was created with public read access.
    anonymous_client = BlobClient.from_blob_url(url)
    downloaded = anonymous_client.download_blob()

    assert downloaded.readall() == b"<html><body>hi</body></html>"
    assert downloaded.properties.content_settings.content_type == "text/html"
