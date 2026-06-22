"""
Custom exception classes and FastAPI exception handlers.
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


# ── Custom Exceptions ────────────────────────────────────

class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(AppException):
    """Resource not found."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(
            message=f"{resource} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class AlreadyExistsException(AppException):
    """Resource already exists."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(
            message=f"{resource} already exists",
            status_code=status.HTTP_409_CONFLICT,
        )


class UnauthorizedException(AppException):
    """Authentication required or failed."""

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(AppException):
    """Insufficient permissions."""

    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ValidationException(AppException):
    """Input validation failed."""

    def __init__(self, message: str = "Validation error"):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class AccountDeletedException(AppException):
    """Account has been soft-deleted."""

    def __init__(self):
        super().__init__(
            message="Account has been deleted. Use the restore endpoint to recover it.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class InvalidOTPException(AppException):
    """OTP is invalid or expired."""

    def __init__(self):
        super().__init__(
            message="Invalid or expired OTP",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# ── Exception Handlers ──────────────────────────────────

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle all custom AppException subclasses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.message,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected errors."""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "An unexpected error occurred",
        },
    )
