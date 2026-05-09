from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AUTH_SERVICE_",
        case_sensitive=False,
    )

    project_name: str = "cognimon-auth-service"
    environment: Literal["local", "development", "staging", "production", "test"] = "local"
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://brainmon:brainmon@localhost:5432/brainmon_auth"
    jwt_secret: str = "change-me-before-production-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_header_name: str = "Authorization"
    jwt_scheme: str = "Bearer"
    metrics_enabled: bool = True
    password_pepper: str = ""
    access_token_expire_minutes: int = 60
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    bootstrap_schema: bool = False

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def normalize_allowed_origins(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned.startswith("[") and cleaned.endswith("]"):
                return [
                    item.strip().strip('"').strip("'")
                    for item in cleaned[1:-1].split(",")
                    if item.strip()
                ]
            return [cleaned]
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if (
            self.environment == "production"
            and self.jwt_secret == "change-me-before-production-32-chars"
        ):
            raise ValueError("A non-default JWT secret is required in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
