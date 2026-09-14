"""Azure Table Storage implementation of `JobRepository`.

A job is stored as one table entity per row. `PartitionKey` is fixed (jobs
are always looked up by id, never queried by partition), and `RowKey` is
the job id.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient

from partikkelspredning.domain.jobs import JobStatus, SimulationJob

_PARTITION_KEY = "job"


class TableJobRepository:
    def __init__(self, connection_string: str, table_name: str = "jobs") -> None:
        service = TableServiceClient.from_connection_string(connection_string)
        self._table = service.create_table_if_not_exists(table_name)

    def create(self, job: SimulationJob) -> None:
        self._table.create_entity(_job_to_entity(job))

    def get(self, job_id: str) -> Optional[SimulationJob]:
        try:
            entity = self._table.get_entity(_PARTITION_KEY, job_id)
        except ResourceNotFoundError:
            return None
        return _entity_to_job(entity)

    def update(self, job: SimulationJob) -> None:
        self._table.update_entity(_job_to_entity(job), mode="replace")


def _job_to_entity(job: SimulationJob) -> Dict[str, Any]:
    return {
        "PartitionKey": _PARTITION_KEY,
        "RowKey": job.job_id,
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


def _entity_to_job(entity: Dict[str, Any]) -> SimulationJob:
    return SimulationJob(
        job_id=entity["RowKey"],
        status=JobStatus(entity["status"]),
        parameters=json.loads(entity["parameters"]) if entity["parameters"] else {},
        user_email=entity["user_email"],
        metadata=json.loads(entity["metadata"]) if entity["metadata"] else {},
        created_at=entity["created_at"],
        updated_at=entity["updated_at"],
        worker_id=entity["worker_id"] or None,
        claimed_at=entity["claimed_at"] or None,
        result_reference=entity["result_reference"] or None,
        error_message=entity["error_message"] or None,
    )
