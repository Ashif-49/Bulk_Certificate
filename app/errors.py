from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger("bulk_cert")


class AppException(Exception):
    """Base application exception supporting HTTP status codes and error keys."""
    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class JobNotFoundException(AppException):
    def __init__(self, job_id: str):
        super().__init__(
            code="JOB_NOT_FOUND",
            message=f"Job with ID '{job_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND
        )


class CertificateNotFoundException(AppException):
    def __init__(self, certificate_id: str):
        super().__init__(
            code="CERTIFICATE_NOT_FOUND",
            message=f"Certificate with ID '{certificate_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND
        )


class CertificateNotReadyException(AppException):
    def __init__(self, certificate_id: str, current_status: str):
        super().__init__(
            code="CERTIFICATE_NOT_READY",
            message=f"Certificate '{certificate_id}' is not generated yet (current status: {current_status}).",
            status_code=status.HTTP_409_CONFLICT
        )


class ValidationException(AppException):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


def register_error_handlers(app):
    """Register FastAPI exception handlers returning consistent error JSON format."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Flatten Pydantic validation errors into readable message
        errors = exc.errors()
        first_err = errors[0] if errors else {}
        loc = " -> ".join(str(l) for l in first_err.get("loc", []))
        msg = first_err.get("msg", "Validation error")
        message = f"Invalid input at {loc}: {msg}" if loc else msg

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "REQUEST_VALIDATION_ERROR", "message": message}}
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        code = "HTTP_ERROR"
        if exc.status_code == 404:
            code = "NOT_FOUND"
        elif exc.status_code == 409:
            code = "CONFLICT"
        elif exc.status_code == 422:
            code = "UNPROCESSABLE_ENTITY"

        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": str(exc.detail)}}
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled server exception: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred."}}
        )
