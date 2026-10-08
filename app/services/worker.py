import os
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Any
from sqlalchemy import update, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Job, Certificate, utc_now
from app.certificates.renderer import render_certificate

logger = logging.getLogger("bulk_cert.worker")


class BackgroundWorker:
    """
    Background worker managing asynchronous certificate generation.
    
    Why: Keeps HTTP request/response cycle fast (<50ms) by offloading PDF generation
    to a background ThreadPool.
    
    Design assumptions & decisions:
    - Single-process model: Designed for a single application process.
    - Idempotency: Processes only 'pending' certificates; recomputes counters from DB COUNT(*).
    - Failure isolation: Each certificate rendered in individual try/except and committed independently.
    - Atomicity: Jobs are claimed via an atomic UPDATE query.
    """

    def __init__(self, max_workers: int = settings.WORKER_THREADS):
        self._executor: Any = ThreadPoolExecutor(max_workers=max_workers)

    def set_executor(self, custom_executor: Any):
        """Allows injecting an inline executor or mock executor during tests."""
        self._executor = custom_executor

    def enqueue_job(self, job_id: str):
        """Enqueue job ID for background processing."""
        self._executor.submit(self.process_job, job_id)

    def process_job(self, job_id: str):
        """
        Process all pending certificates for a given job.
        
        Uses a dedicated thread-local database session. Claims the job atomically
        to prevent race conditions.
        """
        db: Session = SessionLocal()
        try:
            now = utc_now()
            
            # Atomic job claim: only claim if still 'queued'
            # Why: Ensures two concurrent threads or workers cannot process the same job twice
            stmt = (
                update(Job)
                .where(Job.id == job_id, Job.status == "queued")
                .values(status="processing", started_at=now)
            )
            result = db.execute(stmt)
            db.commit()

            if result.rowcount == 0:
                logger.info("Job %s could not be claimed (already processing or finished).", job_id)
                # Verify if job is already in processing status (e.g., resumed or manual call)
                job = db.query(Job).filter(Job.id == job_id).first()
                if not job or job.status not in ("queued", "processing"):
                    return
            else:
                job = db.query(Job).filter(Job.id == job_id).first()

            if not job:
                logger.error("Job %s not found in DB after claim.", job_id)
                return

            # Ensure job-specific storage folder exists
            job_storage_dir = os.path.join(settings.STORAGE_DIR, job.id)
            os.makedirs(job_storage_dir, exist_ok=True)

            # Query only PENDING certificates
            # Why: Makes crash recovery idempotent without reprocessing already generated certificates
            pending_certs = (
                db.query(Certificate)
                .filter(Certificate.job_id == job_id, Certificate.status == "pending")
                .all()
            )

            for cert in pending_certs:
                self._process_single_certificate(db, job, cert, job_storage_dir)

            # Finalize job status based on exact COUNT(*) of generated and failed certificates
            self._finalize_job_status(db, job)

        except Exception as e:
            logger.exception("Unexpected error processing job %s: %s", job_id, e)
            try:
                # Fallback to mark job as failed if uncaught error occurs
                job = db.query(Job).filter(Job.id == job_id).first()
                if job:
                    job.status = "failed"
                    job.finished_at = utc_now()
                    db.commit()
            except Exception:
                db.rollback()
        finally:
            db.close()

    def _process_single_certificate(self, db: Session, job: Job, cert: Certificate, job_storage_dir: str):
        """
        Render and persist an individual certificate.
        
        Why: Per-item isolation ensures one faulty recipient never halts or cancels the batch.
        Atomic file replacement prevents partially written or corrupted PDF reads.
        """
        try:
            render_data = {
                "recipient_name": cert.recipient_name,
                "event_name": job.event_name,
                "issuer_name": job.issuer_name,
                "issue_date": job.issue_date,
                "certificate_number": cert.certificate_number,
                "course_title": cert.course_title,
            }

            # Pure rendering function returns raw bytes
            pdf_bytes = render_certificate(render_data)

            # Atomic write: write to temporary file, then atomic rename
            filename = f"{cert.id}.pdf"
            temp_path = os.path.join(job_storage_dir, f"{cert.id}.tmp")
            final_path = os.path.join(job_storage_dir, filename)

            with open(temp_path, "wb") as f:
                f.write(pdf_bytes)
            os.replace(temp_path, final_path)

            # Store file path relative to STORAGE_DIR to prevent directory traversal
            cert.file_path = f"{job.id}/{filename}"
            cert.status = "generated"
            cert.error_message = None
            cert.generated_at = utc_now()

        except Exception as exc:
            logger.exception("Failed generating certificate for %s (id: %s): %s", cert.recipient_email, cert.id, exc)
            cert.status = "failed"
            cert.error_message = f"Generation failed: {str(exc)}"

        finally:
            # Commit individual item immediately
            db.commit()

            # Recompute counters from DB COUNT(*) to maintain source-of-truth consistency
            self._update_job_counters(db, job)

    def _update_job_counters(self, db: Session, job: Job):
        """Recompute succeeded and failed counts from the database."""
        status_counts = dict(
            db.query(Certificate.status, func.count(Certificate.id))
            .filter(Certificate.job_id == job.id)
            .group_by(Certificate.status)
            .all()
        )
        job.succeeded = status_counts.get("generated", 0)
        job.failed = status_counts.get("failed", 0)
        db.commit()

    def _finalize_job_status(self, db: Session, job: Job):
        """Set finished_at timestamp and final status based on aggregated results."""
        status_counts = dict(
            db.query(Certificate.status, func.count(Certificate.id))
            .filter(Certificate.job_id == job.id)
            .group_by(Certificate.status)
            .all()
        )
        succeeded = status_counts.get("generated", 0)
        failed = status_counts.get("failed", 0)
        total = job.total

        job.succeeded = succeeded
        job.failed = failed
        job.finished_at = utc_now()

        if total == 0 or failed == total:
            job.status = "failed"
        elif failed == 0:
            job.status = "completed"
        else:
            job.status = "completed_with_errors"

        db.commit()


# Global worker instance
worker = BackgroundWorker()


def recover_pending_jobs(db: Session):
    """
    Crash recovery on application startup.
    
    Why: If the server crashed or was killed while jobs were in 'processing' or 'queued',
    reset them to 'queued' and enqueue them. The idempotent worker will only process
    the remaining 'pending' certificates.
    """
    interrupted_jobs = (
        db.query(Job)
        .filter(Job.status.in_(["queued", "processing"]))
        .all()
    )
    for j in interrupted_jobs:
        logger.warning("Recovering interrupted job %s (previous status: %s)", j.id, j.status)
        j.status = "queued"
        db.commit()
        worker.enqueue_job(j.id)
