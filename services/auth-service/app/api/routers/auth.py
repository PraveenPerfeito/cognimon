from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_service, get_session, get_settings
from app.core.config import Settings
from app.schemas.auth import AccessTokenResponse, LoginRequest, RegisterRequest
from app.schemas.user import UserProfileResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserProfileResponse:
    user = await auth_service.register_user(session, payload)
    return UserProfileResponse.model_validate(user)


@router.post("/login", response_model=AccessTokenResponse)
async def login_user(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse:
    user = await auth_service.authenticate_user(session, payload.email, payload.password)
    token = auth_service.issue_access_token(user, settings)
    return AccessTokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
    )

