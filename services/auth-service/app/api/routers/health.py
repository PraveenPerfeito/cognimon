from fastapi import APIRouter, Request

from app.schemas.common import HealthResponse

router = APIRouter()


def _build_health_response(request: Request, *, status: str) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status=status,
        service=settings.project_name,
        environment=settings.environment,
        version=settings.service_version,
    )


@router.get("/ready", response_model=HealthResponse)
async def ready(request: Request) -> HealthResponse:
    await request.app.state.db.check_connection()
    return _build_health_response(request, status="ready")


@router.get("/live", response_model=HealthResponse)
async def live(request: Request) -> HealthResponse:
    return _build_health_response(request, status="ok")
