"""FastAPI request/response models.

Kept separate from the domain's `SimulationJob` so the API controls exactly
what's exposed (e.g. no `worker_id`, no internal lease fields - "do not
expose internal implementation details") independently of how the domain
model evolves. The forms-registry endpoints (`GET /`, `GET /forms`) and the
job endpoints below all serve pydantic models directly rather than
duplicating schema classes here - see `api.routes_index` and
`domain.forms.Form`/`domain.parameters.ParameterDefinition`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field

from partikkelspredning.domain.jobs import JobStatus, SimulationJob


class SubmitJobRequest(BaseModel):
    user_email: EmailStr
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    parameters: Dict[str, Any]
    user_email: str
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    result_url: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_domain(cls, job: SimulationJob, *, result_url: Optional[str] = None) -> "JobResponse":
        return cls(
            job_id=job.job_id,
            status=job.status,
            parameters=job.parameters,
            user_email=job.user_email,
            metadata=job.metadata,
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat(),
            result_url=result_url,
            error_message=job.error_message,
        )


class ClaimJobRequest(BaseModel):
    worker_id: str


class ClaimedJobResponse(BaseModel):
    job_id: str
    parameters: Dict[str, Any]
    user_email: str
    metadata: Dict[str, Any]


class CompleteJobRequest(BaseModel):
    worker_id: str
    result_reference: str


class FailJobRequest(BaseModel):
    worker_id: str
    error_message: str
