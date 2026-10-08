from typing import Optional
from fastapi import APIRouter, Depends, status, UploadFile, File, Form, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
    PaginatedCertificatesResponse
)
from app.services import job_service
from app.services.validation import parse_and_validate_csv

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit bulk certificate job via JSON payload"
)
def create_job_json(
    payload: JobCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Submit a bulk certificate generation job with a JSON payload of recipients.
    
    Why HTTP 202: Processing is asynchronous to prevent blocking the HTTP connection
    when handling thousands of recipients.
    """
    raw_recipients = [r.model_dump() for r in payload.recipients]
    job, rejected_count = job_service.create_job(
        db=db,
        event_name=payload.event_name,
        issuer_name=payload.issuer_name,
        issue_date=payload.issue_date,
        raw_recipients=raw_recipients
    )

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        total=job.total,
        rejected_count=rejected_count,
        status_url=f"/api/v1/jobs/{job.id}"
    )


@router.post(
    "/upload",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit bulk certificate job via CSV file upload"
)
async def create_job_csv(
    event_name: str = Form(..., min_length=1, max_length=255),
    issuer_name: str = Form(..., min_length=1, max_length=255),
    issue_date: str = Form(..., min_length=1, max_length=50),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Submit a bulk certificate generation job by uploading a CSV file.
    
    Accepts CSV with headers (case-insensitive): name, email, course_title.
    """
    content = await file.read()
    raw_recipients = parse_and_validate_csv(content)

    job, rejected_count = job_service.create_job(
        db=db,
        event_name=event_name,
        issuer_name=issuer_name,
        issue_date=issue_date,
        raw_recipients=raw_recipients
    )

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        total=job.total,
        rejected_count=rejected_count,
        status_url=f"/api/v1/jobs/{job.id}"
    )


@router.get(
    "/sample-csv",
    summary="Download a sample CSV file template for bulk generation"
)
def download_sample_csv():
    """
    Download a sample CSV template for recipient uploads.
    
    Why: Provides an immediate formatted sample with valid headers and rows.
    """
    csv_text = job_service.get_sample_csv_content()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sample_recipients.csv"'}
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get current job status, counters, and progress"
)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Poll job status, progress percentage, and generation counters."""
    return job_service.get_job_status(db=db, job_id=job_id)


@router.get(
    "/{job_id}/certificates",
    response_model=PaginatedCertificatesResponse,
    summary="List certificates for a job with pagination and status filter"
)
def get_job_certificates(
    job_id: str,
    status: Optional[str] = Query(None, description="Filter by status: pending, generated, failed"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db)
):
    """Retrieve paginated certificates for a job."""
    return job_service.get_job_certificates(
        db=db,
        job_id=job_id,
        status_filter=status,
        limit=limit,
        offset=offset
    )


@router.get(
    "/{job_id}/download",
    summary="Stream a ZIP archive containing all generated certificates and failures.csv"
)
def download_job_zip(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Stream a ZIP archive of all generated certificates.
    
    Why: Uses chunked streaming to avoid storing entire ZIP in server memory.
    """
    zip_stream = job_service.stream_job_zip(db=db, job_id=job_id)
    return StreamingResponse(
        zip_stream,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="certificates_{job_id}.zip"'}
    )
