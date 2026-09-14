"""FastAPI request/response models.

Kept separate from the domain's `SimulationJob` so the API controls exactly
what's exposed (e.g. no `worker_id`, no internal lease fields - "do not
expose internal implementation details") independently of how the domain
model evolves. `ParameterDefinition` itself is the one exception: the
project brief calls for it to be reused as-is by both the form generator
and (here) the `/form` request body, so it is imported directly rather than
duplicated.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field

from partikkelspredning.domain.jobs import JobStatus, SimulationJob
from partikkelspredning.domain.parameters import ParameterDefinition


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


class FormRequest(BaseModel):
    parameters: List[ParameterDefinition]
    title: str = "Submit simulation job"
