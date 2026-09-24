from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Multi-Tenant SaaS Infrastructure"
    DEBUG: bool = True

    # Force explicit IPv4 loopback to avoid Windows IPv6 [::1] connection drops
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "saas_db"

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_secret"

    APP_DB_USER: str = "app_user"
    APP_DB_PASSWORD: str = "app_secret"

    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379

    @computed_field
    @property
    def async_database_uri(self) -> str:
        return (
            f"postgresql+asyncpg://{self.APP_DB_USER}:{self.APP_DB_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def sync_database_uri(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"


settings = Settings()