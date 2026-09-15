from __future__ import annotations

import pytest

from partikkelspredning.composition import build_form_store
from partikkelspredning.config import Settings


def test_build_form_store_rejects_local_mode(tmp_path):
    settings = Settings(
        storage_mode="local",
        api_base_url="http://testserver",
        local_data_dir=tmp_path / "data",
    )

    with pytest.raises(RuntimeError, match="azure"):
        build_form_store(settings)


def test_build_form_store_requires_connection_string_in_azure_mode():
    settings = Settings(
        storage_mode="azure",
        api_base_url="http://testserver",
        azure_storage_connection_string="",
    )

    with pytest.raises(RuntimeError, match="AZURE_STORAGE_CONNECTION_STRING"):
        build_form_store(settings)
