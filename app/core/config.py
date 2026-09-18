from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "HRMS API"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql://postgres:admin@localhost:5432/hrms_db"

    JWT_SECRET_KEY: str = "super_secure_and_secret_jwt_key_for_hrms_application_development_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DEFAULT_GEOFENCE_RADIUS_METERS: int = 100
    MAX_OPTIONAL_HOLIDAYS_PER_YEAR: int = 2

    FIRST_SUPER_ADMIN_EMAIL: str = "admin@company.com"
    FIRST_SUPER_ADMIN_PASSWORD: str = "AdminPassword123!"
    FIRST_SUPER_ADMIN_NAME: str = "System Administrator"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
