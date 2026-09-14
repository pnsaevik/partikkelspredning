"""Local `JobRepository` backed by a single CSV file (via pandas).

Intentionally simple: the whole file is read, modified, and rewritten under
an exclusive lock for every write. That is more than adequate for local
development and tests, and is not meant to become a production database -
see `partikkelspredning.adapters.azure.table_repository` for that.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional, Union

import pandas as pd

from partikkelspredning.adapters.local._file_lock import locked
from partikkelspredning.domain.jobs import JobStatus, SimulationJob

_COLUMNS = [
    "job_id",
    "status",
    "parameters",
    "user_email",
    "metadata",
    "created_at",
    "updated_at",
    "worker_id",
    "claimed_at",
    "result_reference",
    "error_message",
]


class CsvJobRepository:
    def __init__(self, csv_path: Union[Path, str]) -> None:
        self._path = Path(csv_path)
        self._lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._write_all([])

    def create(self, job: SimulationJob) -> None:
        with locked(self._lock_path):
            rows = self._read_all()
            rows.append(job)
            self._write_all(rows)

    def get(self, job_id: str) -> Optional[SimulationJob]:
        with locked(self._lock_path):
            for row in self._read_all():
                if row.job_id == job_id:
                    return row
        return None

    def update(self, job: SimulationJob) -> None:
        with locked(self._lock_path):
            rows = self._read_all()
            for index, row in enumerate(rows):
                if row.job_id == job.job_id:
                    rows[index] = job
                    break
            else:
                raise KeyError(f"Cannot update unknown job {job.job_id!r}")
            self._write_all(rows)

    def _read_all(self) -> List[SimulationJob]:
        if self._path.stat().st_size == 0:
            return []
        df = pd.read_csv(self._path, dtype=str, keep_default_na=False)
        return [_row_to_job(row) for _, row in df.iterrows()]

    def _write_all(self, jobs: List[SimulationJob]) -> None:
        df = pd.DataFrame([_job_to_row(job) for job in jobs], columns=_COLUMNS)
        df.to_csv(self._path, index=False)


def _job_to_row(job: SimulationJob) -> dict:
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "parameters": json.dumps(job.parameters),
        "user_email": job.user_email,
        "metadata": json.dumps(job.metadata),
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "worker_id": job.worker_id or "",
        "claimed_at": job.claimed_at.isoformat() if job.claimed_at else "",
        "result_reference": job.result_reference or "",
        "error_message": job.error_message or "",
    }


def _row_to_job(row: Any) -> SimulationJob:
    return SimulationJob(
        job_id=row["job_id"],
        status=JobStatus(row["status"]),
        parameters=json.loads(row["parameters"]) if row["parameters"] else {},
        user_email=row["user_email"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        worker_id=row["worker_id"] or None,
        claimed_at=row["claimed_at"] or None,
        result_reference=row["result_reference"] or None,
        error_message=row["error_message"] or None,
    )
