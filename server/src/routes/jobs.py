"""Job status lookup."""

from fastapi import APIRouter, HTTPException

from ..deps import dynamo as _dynamo


router = APIRouter()


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = _dynamo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    job.pop("PK", None)
    job.pop("SK", None)
    return job
