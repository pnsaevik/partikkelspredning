"""Runtime configuration.

Everything here is read from environment variables so no Azure resource
names, connection strings, or other secrets are ever hard-coded in source -
see the root README's Security section.

    PARTIKKEL_STORAGE_MODE               "local" (default) or "azure"
    PARTIKKEL_API_BASE_URL               API base URL baked into generated forms
    PARTIKKEL_PARAMETER_DEFINITIONS_PATH JSON file of parameter definitions (optional)
    PARTIKKEL_LOCAL_DATA_DIR             local mode: where CSV/results files live
    AZURE_STORAGE_CONNECTION_STRING      azure mode: shared connection string
    PARTIKKEL_AZURE_TABLE_NAME           azure mode: job metadata table name
    PARTIKKEL_AZURE_QUEUE_NAME           azure mode: job queue name
    PARTIKKEL_AZURE_RESULTS_CONTAINER    azure mode: results blob container name
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from partikkelspredning.domain.parameters import ParameterDefinition

# Used when PARTIKKEL_PARAMETER_DEFINITIONS_PATH isn't set - matches the
# example simulation in the project brief. Real deployments should point
# PARTIKKEL_PARAMETER_DEFINITIONS_PATH at their own definition file instead
# of relying on this default.
_DEFAULT_PARAMETER_DEFINITIONS: List[ParameterDefinition] = [
    ParameterDefinition(name="resolution", type="integer", description="Horizontal grid resolution"),
    ParameterDefinition(name="duration", type="float", description="Simulation duration in days"),
    ParameterDefinition(name="experiment", type="text", description="Name of the experiment"),
]


@dataclass(frozen=True)
class Settings:
    storage_mode: str  # "local" or "azure"
    api_base_url: str
    parameter_definitions: List[ParameterDefinition] = field(
        default_factory=lambda: list(_DEFAULT_PARAMETER_DEFINITIONS)
    )

    # local mode
    local_data_dir: Path = Path("./data")

    # azure mode
    azure_storage_connection_string: str = ""
    azure_table_name: str = "jobs"
    azure_queue_name: str = "jobs"
    azure_results_container: str = "results"


def _load_parameter_definitions() -> List[ParameterDefinition]:
    path = os.environ.get("PARTIKKEL_PARAMETER_DEFINITIONS_PATH")
    if not path:
        return list(_DEFAULT_PARAMETER_DEFINITIONS)
    raw = json.loads(Path(path).read_text())
    return [ParameterDefinition(**item) for item in raw]


def get_settings() -> Settings:
    """Build `Settings` from environment variables."""
    storage_mode = os.environ.get("PARTIKKEL_STORAGE_MODE", "local").lower()
    if storage_mode not in ("local", "azure"):
        raise ValueError(f"Unknown PARTIKKEL_STORAGE_MODE: {storage_mode!r}")
    return Settings(
        storage_mode=storage_mode,
        api_base_url=os.environ.get("PARTIKKEL_API_BASE_URL", "http://localhost:8000"),
        parameter_definitions=_load_parameter_definitions(),
        local_data_dir=Path(os.environ.get("PARTIKKEL_LOCAL_DATA_DIR", "./data")),
        azure_storage_connection_string=os.environ.get("AZURE_STORAGE_CONNECTION_STRING", ""),
        azure_table_name=os.environ.get("PARTIKKEL_AZURE_TABLE_NAME", "jobs"),
        azure_queue_name=os.environ.get("PARTIKKEL_AZURE_QUEUE_NAME", "jobs"),
        azure_results_container=os.environ.get("PARTIKKEL_AZURE_RESULTS_CONTAINER", "results"),
    )
