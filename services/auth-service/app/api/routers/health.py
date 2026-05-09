from fastapi import APIRouter, Request

from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok", service="cognimon-auth-service")


@router.get("/ready", response_model=HealthResponse)
async def ready(request: Request) -> HealthResponse:
    await request.app.state.db.check_connection()
    return HealthResponse(status="ready", service="cognimon-auth-service")
