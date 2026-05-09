import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import AuthServiceError, register_exception_handlers
from app.core.logging import configure_logging
from app.db.database import Database
from app.middleware.jwt import attach_authenticated_user
from app.observability.metrics import ServiceMetrics

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    database = Database(
        app_settings.database_url,
        echo=app_settings.environment in {"local", "development"},
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.settings = app_settings
        application.state.db = database
        if app_settings.bootstrap_schema:
            await database.create_schema()
        logger.info("Starting %s in %s mode.", app_settings.project_name, app_settings.environment)
        try:
            yield
        finally:
            await database.dispose()
            logger.info("Shut down %s.", app_settings.project_name)

    app = FastAPI(
        title="Cognimon Auth Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.db = database
    app.state.metrics = (
        ServiceMetrics(app_settings.project_name)
        if app_settings.metrics_enabled
        else None
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=app_settings.api_v1_prefix)

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        started_at = perf_counter()
        response = None
        try:
            await attach_authenticated_user(request, app_settings)
            response = await call_next(request)
        except AuthServiceError as exc:
            response = JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.message},
                headers=exc.headers,
            )
        status_code = response.status_code if response is not None else 500
        if (
            response is not None
            and response.status_code == 401
            and "WWW-Authenticate" not in response.headers
        ):
            response.headers["WWW-Authenticate"] = app_settings.jwt_scheme
        response.headers["X-Request-ID"] = request_id
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        if app.state.metrics is not None:
            app.state.metrics.observe_request(
                method=request.method,
                path=route_path,
                status_code=status_code,
                duration_seconds=perf_counter() - started_at,
            )
        current_user = getattr(request.state, "authenticated_user", None)
        current_user_id = getattr(current_user, "id", "anonymous")
        logger.info(
            "request_id=%s user_id=%s method=%s path=%s status=%s",
            request_id,
            current_user_id,
            request.method,
            request.url.path,
            status_code,
        )
        return response

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": app_settings.project_name,
            "environment": app_settings.environment,
            "docs": "/docs",
        }

    return app


app = create_app()
