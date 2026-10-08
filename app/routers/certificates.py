from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CertificatePreviewRequest
from app.services import job_service
from app.certificates.renderer import render_certificate

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.post(
    "/preview",
    summary="Generate an ephemeral certificate PDF preview in memory"
)
def preview_certificate(payload: CertificatePreviewRequest):
    """
    Generate an in-memory certificate PDF for real-time frontend layout preview.
    
    Why: Pure in-memory rendering avoids database and disk I/O when organizers
    are previewing templates or checking layout formatting before running batch jobs.
    """
    render_data = {
        "recipient_name": payload.recipient_name or "Jane Doe",
        "event_name": payload.event_name or "Certificate of Achievement",
        "issuer_name": payload.issuer_name or "Global Academy of Excellence",
        "issue_date": payload.issue_date or "2026-10-08",
        "certificate_number": "PREVIEW-2026-SAMPLE",
        "course_title": payload.course_title,
    }
    pdf_bytes = render_certificate(render_data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="certificate_preview.pdf"'}
    )


@router.get(
    "/{certificate_id}/download",
    summary="Download or view an individual generated certificate PDF"
)
def download_certificate(
    certificate_id: str,
    inline: bool = Query(False, description="Display inline in browser rather than forcing download"),
    db: Session = Depends(get_db)
):
    """
    Download or stream a single generated certificate PDF.
    
    Returns 409 if the certificate is still pending or failed.
    Returns 404 if the certificate is unknown.
    """
    file_path, filename = job_service.get_certificate_download_path(db=db, certificate_id=certificate_id)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/pdf",
        content_disposition_type="inline" if inline else "attachment"
    )
