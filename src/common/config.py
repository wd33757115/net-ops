
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.1

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "netops_agent"
    POSTGRES_USER: str = "netops"
    POSTGRES_PASSWORD: str = "netops123456"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300
    CELERY_TASK_TIME_LIMIT: int = 360
    CELERY_MAX_RETRIES: int = 3

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_NAME: str = "netops-files"

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "netops_knowledge"

    FASTAPI_HOST: str = "0.0.0.0"
    FASTAPI_PORT: int = 8000

    STREAMLIT_SERVER_PORT: int = 8501

    LANGFUSE_HOST: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None

    ITSM_WEBHOOK_SECRET: str = "itsm-secret-2026"
    ITSM_CALLBACK_URL: str | None = None

    ENFORCE_BFF_ORIGIN: bool | None = None

    PROJECT_NAME: str = "NetOps-MultiAgent"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    USE_SUPERVISOR_V2: bool = True

    # 与 Django SIMPLE_JWT 共用（默认与 SECRET_KEY 一致，生产务必在 .env 中显式设置）
    JWT_SECRET_KEY: str = "django-insecure-default-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"

    @property
    def postgres_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def postgres_url_asyncpg(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()


def get_settings() -> Settings:
    return settings
