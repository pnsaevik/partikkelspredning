"""Composition root: turns `Settings` into fully wired services/adapters.

This is the one place in the application that knows about every concrete
adapter and picks between them. Everything above it (the API layer) only
ever sees `JobService`/`FormStore` and the ports they depend on.

Job storage (`build_job_service`) is unconditionally Azure - see
FEATURE_PLAN.md's "multiple_forms" AC6/AC7: there is no local job-storage
adapter any more, so this always builds the real Azure adapters (and
therefore always needs `AZURE_STORAGE_CONNECTION_STRING`, regardless of
`Settings.storage_mode`). `Settings.storage_mode` now only selects where
*pre-rendered forms* are stored, via `build_forms_store`.
"""
from __future__ import annotations

from partikkelspredning.config import Settings
from partikkelspredning.ports.form_store import FormStore
from partikkelspredning.services.job_service import JobService


def build_job_service(settings: Settings) -> JobService:
    """Build a `JobService` backed by the real Azure adapters.

    Always Azure - job storage has no local mode (see the module
    docstring). Raises `RuntimeError` if `AZURE_STORAGE_CONNECTION_STRING`
    is missing, and only imports the Azure SDKs once that check passes, so
    an environment without the "azure" extra installed (e.g. the default
    `pytest` CI job, which uses `tests/fakes.py` instead of this function)
    gets a clear `RuntimeError` rather than a `ModuleNotFoundError`.
    """
    connection_string = settings.azure_storage_connection_string
    if not connection_string:
        raise RuntimeError(
            "AZURE_STORAGE_CONNECTION_STRING must be set - job storage is always Azure"
        )

    from partikkelspredning.adapters.azure.blob_result_store import BlobResultStore
    from partikkelspredning.adapters.azure.email_notifications import AzureEmailNotificationService
    from partikkelspredning.adapters.azure.storage_queue import StorageQueueJobQueue
    from partikkelspredning.adapters.azure.table_repository import TableJobRepository

    return JobService(
        repository=TableJobRepository(connection_string, settings.azure_table_name),
        queue=StorageQueueJobQueue(connection_string, settings.azure_queue_name),
        result_store=BlobResultStore(connection_string, settings.azure_results_container),
        notifier=AzureEmailNotificationService(),
    )


def build_form_store(settings: Settings) -> FormStore:
    """Build the `FormStore` used to deploy the single public job-submission form.

    Azure only for this iteration (see FEATURE_PLAN.md's "public_form"
    acceptance criteria) - there is no local-mode form deployment target
    for it. Unrelated to `build_forms_store` below, which is for the
    multiple-forms registry (`services.form_registry`) pre-rendered at
    startup - the two are separate features that happen to share a port.
    """
    if settings.storage_mode != "azure":
        raise RuntimeError(
            "Public form deployment requires PARTIKKEL_STORAGE_MODE=azure "
            f"(got {settings.storage_mode!r})"
        )

    connection_string = settings.azure_storage_connection_string
    if not connection_string:
        raise RuntimeError(
            "AZURE_STORAGE_CONNECTION_STRING must be set when PARTIKKEL_STORAGE_MODE=azure"
        )

    # Imported lazily, and only once the check above passes, so this branch
    # raises a clear RuntimeError - not an azure-package ModuleNotFoundError
    # - when the connection string is missing in an environment where the
    # "azure" extra isn't installed (e.g. the default `pytest` CI job).
    from partikkelspredning.adapters.azure.blob_form_store import BlobFormStore

    return BlobFormStore(connection_string, settings.azure_forms_container)


def build_forms_store(settings: Settings) -> FormStore:
    """Build the `FormStore` used for the multiple-forms registry.

    Unlike `build_form_store` (the single public form, Azure-only), this
    supports a local mode so the forms registry can be pre-rendered and
    served in development and the default test suite with no Azure
    credentials: `Settings.storage_mode == "local"` (the default) returns a
    `LocalFormStore` writing under `settings.forms_local_dir`; `"azure"`
    returns a `BlobFormStore` (reusing the same adapter and
    `azure_forms_container` setting `build_form_store` uses).
    """
    if settings.storage_mode == "local":
        from partikkelspredning.adapters.local.form_store import LocalFormStore

        return LocalFormStore(settings.forms_local_dir)

    if settings.storage_mode == "azure":
        connection_string = settings.azure_storage_connection_string
        if not connection_string:
            raise RuntimeError(
                "AZURE_STORAGE_CONNECTION_STRING must be set when PARTIKKEL_STORAGE_MODE=azure"
            )

        from partikkelspredning.adapters.azure.blob_form_store import BlobFormStore

        return BlobFormStore(connection_string, settings.azure_forms_container)

    raise ValueError(f"Unknown storage mode: {settings.storage_mode!r}")  # pragma: no cover
