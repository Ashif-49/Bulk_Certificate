import os
import re
import csv
import io
import uuid
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

import zipstream

from app.config import settings
from app.models import Job, Certificate, utc_now
from app.schemas import (
    JobStatusResponse,
    CertificateItemResponse,
    PaginatedCertificatesResponse
)
from app.errors import (
    JobNotFoundException,
    CertificateNotFoundException,
    CertificateNotReadyException,
    ValidationException
)
from app.services.validation import validate_recipient_item
from app.services.worker import worker


def sanitize_filename(name: str) -> str:
    """Sanitize string to safe filename characters."""
    sanitized = re.sub(r"[^\w\s-]", "", name).strip()
    return re.sub(r"[-\s]+", "_", sanitized) or "recipient"


def generate_certificate_number() -> str:
    """
    Generate unique, race-free certificate identifier.
    
    Why: Generating at creation time ensures even invalid/failed records receive
    a persistent tracking number without database sequence locks or race conditions.
    """
    date_str = utc_now().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:8].upper()
    return f"CERT-{date_str}-{unique_suffix}"


def create_job(
    db: Session,
    event_name: str,
    issuer_name: str,
    issue_date: str,
    raw_recipients: List[Dict[str, Any]]
) -> Tuple[Job, int]:
    """
    Create a bulk job and certificate records, validating each recipient individually.
    
    Why: Partial failure handling requires separating valid items (queued for generation)
    from invalid items (persisted immediately as failed).
    """
    # 1. Request-level validation
    if not raw_recipients:
        raise ValidationException("Recipients list cannot be empty.", code="EMPTY_RECIPIENTS")

    if len(raw_recipients) > settings.MAX_RECIPIENTS:
        raise ValidationException(
            f"Recipients count ({len(raw_recipients)}) exceeds maximum allowed of {settings.MAX_RECIPIENTS}.",
            code="EXCEEDS_MAX_RECIPIENTS"
        )

    clean_event = event_name.strip()
    clean_issuer = issuer_name.strip()
    clean_date = issue_date.strip()

    if not clean_event or not clean_issuer or not clean_date:
        raise ValidationException("Event name, issuer name, and issue date are required.", code="MISSING_JOB_DETAILS")

    # 2. Recipient-level validation and item initialization
    job_id = str(uuid.uuid4())
    seen_emails: set = set()
    certificates: List[Certificate] = []
    rejected_count = 0

    for item in raw_recipients:
        name = item.get("name")
        email = item.get("email")
        course = item.get("course_title")

        is_valid, err_msg, c_name, c_email, c_course = validate_recipient_item(
            name=name,
            email=email,
            course_title=course,
            seen_emails=seen_emails
        )

        cert_number = generate_certificate_number()

        if is_valid:
            cert = Certificate(
                id=str(uuid.uuid4()),
                job_id=job_id,
                recipient_name=c_name,
                recipient_email=c_email,
                course_title=c_course,
                status="pending",
                certificate_number=cert_number,
                created_at=utc_now()
            )
        else:
            rejected_count += 1
            cert = Certificate(
                id=str(uuid.uuid4()),
                job_id=job_id,
                recipient_name=c_name or "Unknown",
                recipient_email=c_email or "unknown@domain.com",
                course_title=c_course,
                status="failed",
                error_message=err_msg,
                certificate_number=cert_number,
                created_at=utc_now()
            )

        certificates.append(cert)

    total_recipients = len(certificates)
    all_invalid = (rejected_count == total_recipients)

    # 3. Create Job entity
    # Why: If every recipient is invalid, immediately fail the job and do not enqueue to worker.
    initial_status = "failed" if all_invalid else "queued"
    finished_time = utc_now() if all_invalid else None

    job = Job(
        id=job_id,
        event_name=clean_event,
        issuer_name=clean_issuer,
        issue_date=clean_date,
        status=initial_status,
        total=total_recipients,
        succeeded=0,
        failed=rejected_count,
        created_at=utc_now(),
        finished_at=finished_time,
        certificates=certificates
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    # 4. Enqueue for background generation if there are valid items
    if not all_invalid:
        worker.enqueue_job(job.id)

    return job, rejected_count


def get_job_status(db: Session, job_id: str) -> JobStatusResponse:
    """Retrieve detailed progress counters and current status for a job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise JobNotFoundException(job_id)

    total = job.total
    succeeded = job.succeeded
    failed = job.failed
    pending = max(0, total - succeeded - failed)

    progress = round(((succeeded + failed) / total) * 100.0, 1) if total > 0 else 100.0

    return JobStatusResponse(
        id=job.id,
        event_name=job.event_name,
        issuer_name=job.issuer_name,
        issue_date=job.issue_date,
        status=job.status,
        total=total,
        succeeded=succeeded,
        failed=failed,
        pending=pending,
        progress_percent=progress,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at
    )


def get_job_certificates(
    db: Session,
    job_id: str,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> PaginatedCertificatesResponse:
    """Retrieve paginated certificates with optional status filtering."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise JobNotFoundException(job_id)

    query = db.query(Certificate).filter(Certificate.job_id == job_id)
    if status_filter:
        query = query.filter(Certificate.status == status_filter.lower().strip())

    total_count = query.count()
    items = query.order_by(Certificate.created_at).offset(offset).limit(limit).all()

    resp_items = [
        CertificateItemResponse(
            id=c.id,
            job_id=c.job_id,
            recipient_name=c.recipient_name,
            recipient_email=c.recipient_email,
            course_title=c.course_title,
            status=c.status,
            certificate_number=c.certificate_number,
            error_message=c.error_message,
            download_url=f"/api/v1/certificates/{c.id}/download" if c.status == "generated" else None,
            created_at=c.created_at,
            generated_at=c.generated_at
        )
        for c in items
    ]

    return PaginatedCertificatesResponse(
        total=total_count,
        limit=limit,
        offset=offset,
        items=resp_items
    )


def get_certificate_download_path(db: Session, certificate_id: str) -> Tuple[str, str]:
    """
    Locate certificate file and produce download filename.
    
    Why: Validates path stays inside STORAGE_DIR to prevent directory traversal attacks.
    """
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert:
        raise CertificateNotFoundException(certificate_id)

    if cert.status != "generated" or not cert.file_path:
        raise CertificateNotReadyException(certificate_id, cert.status)

    base_storage = os.path.abspath(settings.STORAGE_DIR)
    target_path = os.path.abspath(os.path.join(base_storage, cert.file_path))

    # Path traversal check
    if not target_path.startswith(base_storage):
        raise ValidationException("Invalid certificate file path.", code="INVALID_PATH")

    if not os.path.exists(target_path):
        raise CertificateNotFoundException(certificate_id)

    safe_name = sanitize_filename(cert.recipient_name)
    download_filename = f"{safe_name}_{cert.certificate_number}.pdf"
    return target_path, download_filename


def stream_job_zip(db: Session, job_id: str) -> zipstream.ZipStream:
    """
    Stream a ZIP archive containing all generated PDFs and a failures.csv report.
    
    Why: Uses zipstream-ng generator to stream bytes in chunks without loading
    the full ZIP or all PDFs into memory.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise JobNotFoundException(job_id)

    certificates = (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .order_by(Certificate.created_at)
        .all()
    )

    zs = zipstream.ZipStream()
    base_storage = os.path.abspath(settings.STORAGE_DIR)

    # Track used filenames inside the ZIP to prevent duplicates
    used_names: Dict[str, int] = {}
    failed_items = []

    for cert in certificates:
        if cert.status == "generated" and cert.file_path:
            abs_path = os.path.abspath(os.path.join(base_storage, cert.file_path))
            if os.path.exists(abs_path) and abs_path.startswith(base_storage):
                clean_name = sanitize_filename(cert.recipient_name)
                base_zip_name = f"{clean_name}_{cert.certificate_number}.pdf"
                
                # Deduplicate name if collision
                if base_zip_name in used_names:
                    used_names[base_zip_name] += 1
                    arcname = f"{clean_name}_{cert.certificate_number}_{used_names[base_zip_name]}.pdf"
                else:
                    used_names[base_zip_name] = 0
                    arcname = base_zip_name

                zs.add_path(abs_path, arcname)
        elif cert.status == "failed":
            failed_items.append(cert)

    # Include job summary metadata report
    summary_text = (
        f"Bulk Certificate Job Export Summary\n"
        f"-----------------------------------\n"
        f"Job ID: {job.id}\n"
        f"Event Name: {job.event_name}\n"
        f"Issuer: {job.issuer_name}\n"
        f"Issue Date: {job.issue_date}\n"
        f"Status: {job.status}\n"
        f"Total Records: {job.total}\n"
        f"Succeeded: {job.succeeded}\n"
        f"Failed: {job.failed}\n"
        f"Export Timestamp (UTC): {utc_now().isoformat()}\n"
    )
    zs.add(summary_text.encode("utf-8"), "job_summary.txt")

    # Always include failures.csv if any items failed
    if failed_items:
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["recipient_name", "recipient_email", "course_title", "certificate_number", "error_message"])
        for f_cert in failed_items:
            writer.writerow([
                f_cert.recipient_name,
                f_cert.recipient_email,
                f_cert.course_title or "",
                f_cert.certificate_number,
                f_cert.error_message or "Unknown failure"
            ])
        zs.add(csv_buffer.getvalue().encode("utf-8"), "failures.csv")

    return zs


def get_sample_csv_content() -> str:
    """
    Generate sample CSV template with standard header and example rows.
    
    Why: Keeps CSV structure centralized in service layer and accessible to routers.
    """
    return (
        "name,email,course_title\r\n"
        "Jane Doe,jane.doe@example.com,Advanced Machine Learning\r\n"
        "John Smith,john.smith@example.com,Cloud Architecture\r\n"
        "Alex Rivera,alex.rivera@example.com,Cybersecurity Defense\r\n"
        "Maria Garcia,maria.garcia@example.com,Data Science Fundamentals\r\n"
    )
