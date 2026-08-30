import os
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Discipline OS API"
    app_version: str = "0.1.0"
    debug: bool = False

    mongodb_uri: str = ""
    mongodb_username: str = ""
    mongodb_password: str = ""
    mongodb_cluster: str = ""
    mongodb_db_name: str = "habit"

    jwt_secret_key: str = "dev-only-change-me-before-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def fill_from_os_environ(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        for field, env_key in (
            ("mongodb_uri", "MONGODB_URI"),
            ("mongodb_username", "MONGODB_USERNAME"),
            ("mongodb_password", "MONGODB_PASSWORD"),
            ("mongodb_cluster", "MONGODB_CLUSTER"),
            ("jwt_secret_key", "JWT_SECRET_KEY"),
        ):
            if not data.get(field):
                value = os.environ.get(env_key)
                if value:
                    data[field] = value

        return data

    @model_validator(mode="after")
    def ensure_mongodb_uri(self) -> "Settings":
        if self.mongodb_uri:
            return self

        if self.mongodb_username and self.mongodb_password and self.mongodb_cluster:
            user = quote_plus(self.mongodb_username)
            password = quote_plus(self.mongodb_password)
            self.mongodb_uri = f"mongodb+srv://{user}:{password}@{self.mongodb_cluster}"

        if not self.mongodb_uri:
            raise ValueError(
                "Set MONGODB_URI or MONGODB_USERNAME + MONGODB_PASSWORD + MONGODB_CLUSTER"
            )

        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
