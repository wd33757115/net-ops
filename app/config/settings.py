# app/config/settings.py
from dotenv import load_dotenv
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    # LLM 配置
    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: str = "sk-4807b57b90d4429ba727bb178dc45f6f"     
                    # 必须填写

    # PostgreSQL (用于 LangGraph Checkpoint)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "netops_agent"
    POSTGRES_USER: str = "netops"
    POSTGRES_PASSWORD: str = "netops123456"

    # 项目配置
    PROJECT_NAME: str = "NetOps-MultiAgent"
    DEBUG: bool = True

    @property
    def postgres_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


settings = Settings()


def get_settings() -> Settings:
    return settings