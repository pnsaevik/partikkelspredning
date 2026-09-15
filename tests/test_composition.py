from __future__ import annotations

import pytest

from partikkelspredning.adapters.local.form_store import LocalFormStore
from partikkelspredning.composition import build_form_store, build_forms_store, build_job_service
from partikkelspredning.config import Settings


def test_build_job_service_requires_connection_string_in_azure_mode():
    settings = Settings(
        storage_mode="azure",
        api_base_url="http://testserver",
        azure_storage_connection_string="",
    )

    with pytest.raises(RuntimeError, match="AZURE_STORAGE_CONNECTION_STRING"):
        build_job_service(settings)


def test_build_form_store_rejects_local_mode(tmp_path):
    settings = Settings(
        storage_mode="local",
        api_base_url="http://testserver",
        forms_local_dir=tmp_path / "forms",
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


def test_build_forms_store_returns_local_form_store_in_local_mode(tmp_path):
    settings = Settings(
        storage_mode="local",
        api_base_url="http://testserver",
        forms_local_dir=tmp_path / "forms",
    )

    store = build_forms_store(settings)

    assert isinstance(store, LocalFormStore)
    url = store.upload_form_html("example", "<html></html>")
    assert (tmp_path / "forms" / "example.html").read_text() == "<html></html>"
    assert url == str(tmp_path / "forms" / "example.html")


def test_build_forms_store_requires_connection_string_in_azure_mode():
    settings = Settings(
        storage_mode="azure",
        api_base_url="http://testserver",
        azure_storage_connection_string="",
    )

    with pytest.raises(RuntimeError, match="AZURE_STORAGE_CONNECTION_STRING"):
        build_forms_store(settings)
