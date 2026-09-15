"""Composition root: turns `Settings` into a fully wired `JobService`.

This is the one place in the application that knows about every concrete
adapter, local and Azure, and picks between them based on
`Settings.storage_mode`. Everything above it (the API layer) only ever sees
the `JobService` and the ports it depends on.
"""
from __future__ import annotations

from partikkelspredning.adapters.local.console_notifications import ConsoleNotificationService
from partikkelspredning.adapters.local.csv_queue import CsvJobQueue
from partikkelspredning.adapters.local.csv_repository import CsvJobRepository
from partikkelspredning.adapters.local.filesystem_result_store import FilesystemResultStore
from partikkelspredning.config import Settings
from partikkelspredning.ports.form_store import FormStore
from partikkelspredning.services.job_service import JobService


def build_job_service(settings: Settings) -> JobService:
    if settings.storage_mode == "local":
        data_dir = settings.local_data_dir
        repository = CsvJobRepository(data_dir / "jobs.csv")
        queue = CsvJobQueue(data_dir / "queue.txt")
        result_store = FilesystemResultStore(data_dir / "results")
        notifier = ConsoleNotificationService()

    elif settings.storage_mode == "azure":
        # Imported lazily so the azure-* packages are only required when
        # this mode is actually selected - they aren't installed for local
        # dev or the default test suite (see pyproject.toml's "azure" extra
        # and the root README).
        from partikkelspredning.adapters.azure.blob_result_store import BlobResultStore
        from partikkelspredning.adapters.azure.email_notifications import AzureEmailNotificationService
        from partikkelspredning.adapters.azure.storage_queue import StorageQueueJobQueue
        from partikkelspredning.adapters.azure.table_repository import TableJobRepository

        connection_string = settings.azure_storage_connection_string
        if not connection_string:
            raise RuntimeError(
                "AZURE_STORAGE_CONNECTION_STRING must be set when PARTIKKEL_STORAGE_MODE=azure"
            )
        repository = TableJobRepository(connection_string, settings.azure_table_name)
        queue = StorageQueueJobQueue(connection_string, settings.azure_queue_name)
        result_store = BlobResultStore(connection_string, settings.azure_results_container)
        notifier = AzureEmailNotificationService()

    else:  # pragma: no cover - Settings.storage_mode is already validated in get_settings()
        raise ValueError(f"Unknown storage mode: {settings.storage_mode!r}")

    return JobService(
        repository=repository,
        queue=queue,
        result_store=result_store,
        notifier=notifier,
    )


def build_form_store(settings: Settings) -> FormStore:
    """Build the `FormStore` used to deploy the public job-submission form.

    Azure only for this iteration (see FEATURE_PLAN.md's "public_form"
    acceptance criteria) - there is no local-mode form deployment target.
    """
    if settings.storage_mode != "azure":
        raise RuntimeError(
            "Public form deployment requires PARTIKKEL_STORAGE_MODE=azure "
            f"(got {settings.storage_mode!r})"
        )

    # Imported lazily, same reasoning as build_job_service's azure branch.
    from partikkelspredning.adapters.azure.blob_form_store import BlobFormStore

    connection_string = settings.azure_storage_connection_string
    if not connection_string:
        raise RuntimeError(
            "AZURE_STORAGE_CONNECTION_STRING must be set when PARTIKKEL_STORAGE_MODE=azure"
        )
    return BlobFormStore(connection_string, settings.azure_forms_container)
