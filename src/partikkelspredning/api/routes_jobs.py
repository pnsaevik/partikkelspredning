"""HTTP routes for job submission and the compute-worker job lifecycle.

Translates between HTTP and `JobService`/domain errors only - no business
logic lives here. See the root README for the full lifecycle and API
documentation (also available live via FastAPI's generated OpenAPI docs).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from partikkelspredning.api.dependencies import get_job_service
from partikkelspredning.api.schemas import (
    ClaimedJobResponse,
    ClaimJobRequest,
    CompleteJobRequest,
    FailJobRequest,
    JobResponse,
    SubmitJobRequest,
)
from partikkelspredning.api.security import require_worker_auth
from partikkelspredning.domain.errors import (
    InvalidTransitionError,
    JobNotFoundError,
    JobOwnershipError,
)
from partikkelspredning.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def submit_job(request: SubmitJobRequest, job_service: JobService = Depends(get_job_service)) -> JobResponse:
    """Enqueue a new job. `parameters` is accepted as-is, an arbitrary JSON
    object with no predefined schema - see `JobService.submit_job`."""
    job = job_service.submit_job(
        user_email=request.user_email,
        parameters=request.parameters,
        metadata=request.metadata,
    )
    return JobResponse.from_domain(job)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, job_service: JobService = Depends(get_job_service)) -> JobResponse:
    """Look up a job's current state. An unrecognized `job_id` is just a 404 -
    it is never trusted to mean anything else."""
    try:
        job = job_service.get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JobResponse.from_domain(job, result_url=job_service.resolve_result_url(job))


@router.post(
    "/claim",
    response_model=ClaimedJobResponse,
    responses={204: {"description": "No queued job is currently available"}},
    dependencies=[Depends(require_worker_auth)],
)
def claim_job(request: ClaimJobRequest, job_service: JobService = Depends(get_job_service)):
    """For the future compute server: atomically claim one queued job.

    Returns 204 with no body if nothing is queued. See `require_worker_auth`
    for where authentication for this endpoint should be added.
    """
    job = job_service.claim_job(worker_id=request.worker_id)
    if job is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return ClaimedJobResponse(
        job_id=job.job_id,
        parameters=job.parameters,
        user_email=job.user_email,
        metadata=job.metadata,
    )


@router.post(
    "/{job_id}/complete",
    response_model=JobResponse,
    dependencies=[Depends(require_worker_auth)],
)
def complete_job(
    job_id: str, request: CompleteJobRequest, job_service: JobService = Depends(get_job_service)
) -> JobResponse:
    """For the future compute server: report that a claimed job completed successfully."""
    try:
        job = job_service.complete_job(
            job_id=job_id, worker_id=request.worker_id, result_reference=request.result_reference
        )
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (InvalidTransitionError, JobOwnershipError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JobResponse.from_domain(job, result_url=job_service.resolve_result_url(job))


@router.post(
    "/{job_id}/fail",
    response_model=JobResponse,
    dependencies=[Depends(require_worker_auth)],
)
def fail_job(
    job_id: str, request: FailJobRequest, job_service: JobService = Depends(get_job_service)
) -> JobResponse:
    """For the future compute server: report that a claimed job failed."""
    try:
        job = job_service.fail_job(job_id=job_id, worker_id=request.worker_id, error_message=request.error_message)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (InvalidTransitionError, JobOwnershipError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JobResponse.from_domain(job)
