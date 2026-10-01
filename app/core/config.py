from urllib.parse import quote_plus
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Multi-Tenant SaaS Infrastructure"
    DEBUG: bool = True

    # Force explicit IPv4 loopback to avoid Windows/container IPv6 [::1] connection timeouts
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "saas_db"

    # Superuser credentials (DDL, schema creation, Alembic)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_secret"

    # Runtime credentials (strictly scoped under PostgreSQL RLS)
    APP_DB_USER: str = "app_user"
    APP_DB_PASSWORD: str = "app_secret"

    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379

    @computed_field
    @property
    def async_database_uri(self) -> str:
        user = quote_plus(self.APP_DB_USER)
        password = quote_plus(self.APP_DB_PASSWORD)
        return (
            f"postgresql+asyncpg://{user}:{password}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def sync_database_uri(self) -> str:
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return (
            f"postgresql://{user}:{password}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"


settings = Settings()