import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.errors import register_error_handlers
from app.routers import jobs, certificates
from app.services.worker import recover_pending_jobs, worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan hook managing startup table creation and crash recovery.
    
    Why: Automatically initializes SQLite/PostgreSQL schemas and re-enqueues
    interrupted jobs without external migration requirements.
    """
    # 1. Ensure DB tables exist
    Base.metadata.create_all(bind=engine)

    # 2. Crash recovery: re-enqueue jobs that were left in queued or processing state
    db = SessionLocal()
    try:
        recover_pending_jobs(db)
    finally:
        db.close()

    yield

    # Shutdown background worker cleanly
    worker._executor.shutdown(wait=False)


app = FastAPI(
    title="Bulk Certificate Generator API",
    description="High-performance, explainable backend for bulk PDF certificate issuance.",
    version="1.0.0",
    lifespan=lifespan
)

# Register standardized error handlers
register_error_handlers(app)

# Include API Routers under /api/v1
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(certificates.router, prefix="/api/v1")


@app.get("/health", tags=["System"])
@app.get("/api/v1/health", tags=["System"])
def health_check():
    """Health check endpoint verifying system responsiveness."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected"
    }


# Mount static files for the single-page frontend UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
