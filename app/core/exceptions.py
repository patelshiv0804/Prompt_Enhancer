from fastapi import Request
from fastapi.responses import JSONResponse


class AlreadyExistsException(Exception):
    def __init__(self, message: str = "Resource already exists"):
        self.message = message
        super().__init__(self.message)


class InvalidOTPException(Exception):
    def __init__(self, message: str = "Invalid or expired OTP"):
        self.message = message
        super().__init__(self.message)


class NotFoundException(Exception):
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(self.message)


class UnauthorizedException(Exception):
    def __init__(self, message: str = "Unauthorized access"):
        self.message = message
        super().__init__(self.message)


from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    if isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )
    if isinstance(exc, AlreadyExistsException):
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message},
        )
    if isinstance(exc, InvalidOTPException):
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message},
        )
    if isinstance(exc, NotFoundException):
        return JSONResponse(
            status_code=404,
            content={"detail": exc.message},
        )
    if isinstance(exc, UnauthorizedException):
        return JSONResponse(
            status_code=401,
            content={"detail": exc.message},
        )

    logger.error("Unhandled exception processing request %s: %s", request.url.path, exc, exc_info=True)
    detail_msg = str(exc) if settings.environment.lower() == "development" and str(exc) else "An internal server error occurred."
    return JSONResponse(
        status_code=500,
        content={"detail": detail_msg},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return await http_error_handler(request, exc)

