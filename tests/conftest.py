from __future__ import annotations

import pytest

from fakes import FakeResultStore, InMemoryJobQueue, InMemoryJobRepository, RecordingNotificationService
from partikkelspredning.config import Settings
from partikkelspredning.domain.parameters import ParameterDefinition
from partikkelspredning.services.job_service import JobService

PARAMETER_DEFINITIONS = [
    ParameterDefinition(name="resolution", type="integer", description="Horizontal grid resolution"),
    ParameterDefinition(name="duration", type="float", description="Simulation duration in days"),
    ParameterDefinition(name="experiment", type="text", description="Name of the experiment"),
]


@pytest.fixture
def parameter_definitions():
    return PARAMETER_DEFINITIONS


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
        parameter_definitions=PARAMETER_DEFINITIONS,
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
        parameter_definitions=PARAMETER_DEFINITIONS,
        local_data_dir=tmp_path / "data",
    )
