from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.db.models import UserRole


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class UserListResponse(BaseModel):
    count: int
    items: list[UserProfileResponse]

