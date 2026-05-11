from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_service, get_session, get_settings
from app.core.config import Settings
from app.schemas.auth import (
    LoginRequest,
    PasswordResetRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPairResponse,
)
from app.schemas.common import MessageResponse
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


@router.post("/login", response_model=TokenPairResponse)
async def login_user(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> TokenPairResponse:
    user = await auth_service.authenticate_user(session, payload.email, payload.password)
    return TokenPairResponse(
        access_token=auth_service.issue_access_token(user, settings),
        refresh_token=auth_service.issue_refresh_token(user, settings),
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_password_reset(
    payload: PasswordResetRequest,
@router.post("/logout", response_model=MessageResponse)
async def logout_user(
    payload: LogoutRequest,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    await auth_service.request_password_reset(session, payload, settings)
    return MessageResponse(
        detail="If an active account exists for that email, a reset token has been issued."
    )
    await auth_service.revoke_refresh_token(session, payload.refresh_token, settings)
    return MessageResponse(detail="Refresh token revoked.")


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_user_token(
    payload: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> TokenPairResponse:
    user = await auth_service.authenticate_refresh_token(
        session,
        payload.refresh_token,
        settings,
    )
    return TokenPairResponse(
        access_token=auth_service.issue_access_token(user, settings),
        refresh_token=auth_service.issue_refresh_token(user, settings),
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=settings.refresh_token_expire_days * 24 * 60 * 60,
    )

