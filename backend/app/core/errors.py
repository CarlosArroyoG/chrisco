from fastapi import Request, status
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Error de regla de negocio. La capa de servicios lo lanza; main.py lo traduce a HTTP."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class Unauthorized(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED


class NotFound(DomainError):
    status_code = status.HTTP_404_NOT_FOUND


class Conflict(DomainError):
    status_code = status.HTTP_409_CONFLICT


class Forbidden(DomainError):
    status_code = status.HTTP_403_FORBIDDEN


class InvalidInput(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
