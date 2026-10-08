from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Job(Base):
    """Job model representing a bulk certificate generation request."""
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_name = Column(String(255), nullable=False)
    issuer_name = Column(String(255), nullable=False)
    issue_date = Column(String(50), nullable=False)
    
    # Statuses: queued | processing | completed | completed_with_errors | failed
    status = Column(String(30), default="queued", nullable=False, index=True)
    
    total = Column(Integer, default=0, nullable=False)
    succeeded = Column(Integer, default=0, nullable=False)
    failed = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    certificates = relationship(
        "Certificate",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Certificate.created_at"
    )


class Certificate(Base):
    """Certificate model representing an individual recipient's certificate."""
    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    recipient_name = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    course_title = Column(String(255), nullable=True)

    # Statuses: pending | generated | failed
    status = Column(String(30), default="pending", nullable=False, index=True)
    
    # Relative path from STORAGE_DIR (e.g. {job_id}/{certificate_id}.pdf) to prevent path traversal
    file_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Unique certificate number assigned upfront at creation (e.g. CERT-2026-XXXXX)
    certificate_number = Column(String(100), unique=True, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("Job", back_populates="certificates")

    __table_args__ = (
        Index("ix_certificates_job_status", "job_id", "status"),
    )
