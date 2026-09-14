from __future__ import annotations

import pytest

from fakes import FakeResultStore, InMemoryJobQueue, InMemoryJobRepository, RecordingNotificationService
from partikkelspredning.config import Settings
from partikkelspredning.services.job_service import JobService


@pytest.fixture
def repository():
    return InMemoryJobRepository()


@pytest.fixture
def queue():
    return InMemoryJobQueue()


@pytest.fixture
def result_store():
    return FakeResultStore()


@pytest.fixture
def notifier():
    return RecordingNotificationService()


@pytest.fixture
def job_service(repository, queue, result_store, notifier):
    """A JobService wired with fast, in-memory fakes (see tests/fakes.py)."""
    return JobService(
        repository=repository,
        queue=queue,
        result_store=result_store,
        notifier=notifier,
    )


@pytest.fixture
def local_settings(tmp_path):
    """Settings for a real, tmp-dir-backed local deployment (CSV files etc.)."""
    return Settings(
        storage_mode="local",
        api_base_url="http://testserver",
        local_data_dir=tmp_path / "data",
    )
