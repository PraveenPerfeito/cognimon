from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, require_roles
from app.db.models import User, UserRole
from app.repositories.users import UserRepository
from app.schemas.user import UserListResponse, UserProfileResponse

router = APIRouter()


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    return UserProfileResponse.model_validate(current_user)


@router.get("/admin", response_model=UserListResponse)
async def list_users_for_admin(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(UserRole.admin)),
) -> UserListResponse:
    users = await UserRepository().list_users(session)
    return UserListResponse(
        count=len(users),
        items=[UserProfileResponse.model_validate(user) for user in users],
    )

