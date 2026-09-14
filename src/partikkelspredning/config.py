"""Runtime configuration.

Everything here is read from environment variables so no Azure resource
names, connection strings, or other secrets are ever hard-coded in source -
see the root README's Security section.

    PARTIKKEL_STORAGE_MODE               "local" (default) or "azure"
    PARTIKKEL_API_BASE_URL               API base URL baked into generated forms
    PARTIKKEL_LOCAL_DATA_DIR             local mode: where CSV/results files live
    AZURE_STORAGE_CONNECTION_STRING      azure mode: shared connection string
    PARTIKKEL_AZURE_TABLE_NAME           azure mode: job metadata table name
    PARTIKKEL_AZURE_QUEUE_NAME           azure mode: job queue name
    PARTIKKEL_AZURE_RESULTS_CONTAINER    azure mode: results blob container name

There is deliberately no setting here for a job parameter schema - `POST
/jobs` accepts parameters as an arbitrary JSON object with no predefined,
server-configured shape (see `partikkelspredning.domain.parameters`).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    storage_mode: str  # "local" or "azure"
    api_base_url: str

    # local mode
    local_data_dir: Path = Path("./data")

    # azure mode
    azure_storage_connection_string: str = ""
    azure_table_name: str = "jobs"
    azure_queue_name: str = "jobs"
    azure_results_container: str = "results"


def get_settings() -> Settings:
    """Build `Settings` from environment variables."""
    storage_mode = os.environ.get("PARTIKKEL_STORAGE_MODE", "local").lower()
    if storage_mode not in ("local", "azure"):
        raise ValueError(f"Unknown PARTIKKEL_STORAGE_MODE: {storage_mode!r}")
    return Settings(
        storage_mode=storage_mode,
        api_base_url=os.environ.get("PARTIKKEL_API_BASE_URL", "http://localhost:8000"),
        local_data_dir=Path(os.environ.get("PARTIKKEL_LOCAL_DATA_DIR", "./data")),
        azure_storage_connection_string=os.environ.get("AZURE_STORAGE_CONNECTION_STRING", ""),
        azure_table_name=os.environ.get("PARTIKKEL_AZURE_TABLE_NAME", "jobs"),
        azure_queue_name=os.environ.get("PARTIKKEL_AZURE_QUEUE_NAME", "jobs"),
        azure_results_container=os.environ.get("PARTIKKEL_AZURE_RESULTS_CONTAINER", "results"),
    )
