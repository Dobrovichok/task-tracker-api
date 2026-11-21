from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class EnvironmentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )


class DatabaseSettings(EnvironmentSettings):
    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_user: str = "task_tracker"
    postgres_db: str = "task_tracker"
    postgres_password: SecretStr = Field(min_length=1)

    @property
    def url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


class AuthSettings(EnvironmentSettings):
    jwt_secret: SecretStr = Field(min_length=32)
    access_token_minutes: int = Field(default=30, ge=1, le=120)


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
