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
def settings(tmp_path):
    """`Settings` for tests: local forms storage (a scratch tmp dir), no Azure
    credentials - job storage always requires Azure now (see
    `partikkelspredning.composition.build_job_service`), so HTTP-layer tests
    inject a fakes-backed `JobService` directly instead of going through the
    composition root (see `job_service` above and its use in
    `tests/test_api.py`/`tests/test_function_app.py`)."""
    return Settings(
        storage_mode="local",
        api_base_url="http://testserver",
        forms_local_dir=tmp_path / "forms",
    )
