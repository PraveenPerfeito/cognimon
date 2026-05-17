from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        has_upper = any(character.isupper() for character in value)
        has_lower = any(character.islower() for character in value)
        has_digit = any(character.isdigit() for character in value)
        if not (has_upper and has_lower and has_digit):
            raise ValueError("Password must include upper, lower, and numeric characters.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=32)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        has_upper = any(character.isupper() for character in value)
        has_lower = any(character.islower() for character in value)
        has_digit = any(character.isdigit() for character in value)
        if not (has_upper and has_lower and has_digit):
            raise ValueError("Password must include upper, lower, and numeric characters.")
        return value


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
