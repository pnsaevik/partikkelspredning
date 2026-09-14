"""Local `ResultStore` that resolves results to `file://` URLs under a directory.

`result_reference` is expected to be a path relative to `results_dir`; this
mirrors how `partikkelspredning.adapters.azure.blob_result_store` treats a
reference as a blob name relative to a container, so the same reference
format works against either adapter.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union


class FilesystemResultStore:
    def __init__(self, results_dir: Union[Path, str]) -> None:
        self._results_dir = Path(results_dir)
        self._results_dir.mkdir(parents=True, exist_ok=True)

    def build_result_url(self, job_id: str, result_reference: str) -> str:
        path = (self._results_dir / result_reference).resolve()
        return path.as_uri()
