from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AuthServiceError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthenticationError(AuthServiceError):
    status_code = status.HTTP_401_UNAUTHORIZED


class AuthorizationError(AuthServiceError):
    status_code = status.HTTP_403_FORBIDDEN


class ConflictError(AuthServiceError):
    status_code = status.HTTP_409_CONFLICT


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthServiceError)
    async def handle_service_error(_: Request, exc: AuthServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

