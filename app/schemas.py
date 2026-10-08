from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, field_validator


class RecipientInput(BaseModel):
    """Input payload for a single recipient."""
    name: str = Field(..., min_length=1, max_length=100, description="Recipient full name")
    email: str = Field(..., min_length=3, max_length=255, description="Recipient email address")
    course_title: Optional[str] = Field(None, max_length=255, description="Course or distinction title")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Recipient name cannot be empty or only whitespace")
        return v

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Recipient email cannot be empty or only whitespace")
        return v


class JobCreateRequest(BaseModel):
    """Payload to create a new bulk certificate generation job."""
    event_name: str = Field(..., min_length=1, max_length=255, description="Event or certification title")
    issuer_name: str = Field(..., min_length=1, max_length=255, description="Name of issuer organization or person")
    issue_date: str = Field(..., min_length=1, max_length=50, description="Issue date (e.g., YYYY-MM-DD)")
    recipients: List[RecipientInput] = Field(..., min_length=1, description="List of recipient details")

    @field_validator("event_name", "issuer_name", "issue_date", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Field cannot be empty or only whitespace")
        return v


class JobCreateResponse(BaseModel):
    """Response returned upon successfully accepting a job (HTTP 202)."""
    job_id: str
    status: str
    total: int
    rejected_count: int
    status_url: str


class JobStatusResponse(BaseModel):
    """Detailed progress and status for a job."""
    id: str
    event_name: str
    issuer_name: str
    issue_date: str
    status: str
    total: int
    succeeded: int
    failed: int
    pending: int
    progress_percent: float
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class CertificateItemResponse(BaseModel):
    """Item detail in paginated certificate queries."""
    id: str
    job_id: str
    recipient_name: str
    recipient_email: str
    course_title: Optional[str] = None
    status: str
    certificate_number: str
    error_message: Optional[str] = None
    download_url: Optional[str] = None
    created_at: datetime
    generated_at: Optional[datetime] = None


class PaginatedCertificatesResponse(BaseModel):
    """Paginated list of certificates for a job."""
    total: int
    limit: int
    offset: int
    items: List[CertificateItemResponse]


class CertificatePreviewRequest(BaseModel):
    """Payload to preview a certificate without saving to database."""
    recipient_name: Optional[str] = Field("Jane Doe", max_length=100, description="Sample recipient name")
    event_name: Optional[str] = Field("Certificate of Achievement", max_length=255, description="Sample event name")
    issuer_name: Optional[str] = Field("Global Academy of Excellence", max_length=255, description="Sample issuer name")
    issue_date: Optional[str] = Field("2026-10-08", max_length=50, description="Sample issue date")
    course_title: Optional[str] = Field("Advanced Cloud & Software Engineering", max_length=255, description="Sample course title")


class ErrorDetail(BaseModel):
    """Standardized error object structure."""
    code: str
    message: str


class StandardErrorResponse(BaseModel):
    """Top-level error payload: {"error": {"code": "...", "message": "..."}}."""
    error: ErrorDetail
