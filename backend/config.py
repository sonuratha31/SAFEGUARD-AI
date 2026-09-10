"""
SAFEGUARD AI - Application Configuration
Loads all settings from environment variables.
"""
import os
from typing import List
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = Field(default="sqlite:///./safeguard.db")

    # IBM WatsonX
    IBM_WATSONX_API_KEY: str = Field(default="")
    IBM_WATSONX_PROJECT_ID: str = Field(default="")
    IBM_WATSONX_URL: str = Field(default="https://us-south.ml.cloud.ibm.com")
    IBM_LLM_MODEL_ID: str = Field(default="ibm/granite-13b-instruct-v2")
    IBM_EMBEDDING_MODEL_ID: str = Field(default="ibm/slate-125m-english-rtrvr")

    # IBM Langflow
    LANGFLOW_BASE_URL: str = Field(default="http://localhost:7860")
    LANGFLOW_API_KEY: str = Field(default="")
    LANGFLOW_FLOW_ID_RAG: str = Field(default="")
    LANGFLOW_FLOW_ID_AGENT: str = Field(default="")

    # IBM Orchestrate
    IBM_ORCHESTRATE_API_KEY: str = Field(default="")
    IBM_ORCHESTRATE_INSTANCE_URL: str = Field(default="")

    # Vector Database
    VECTOR_DB_TYPE: str = Field(default="chroma")
    CHROMA_PERSIST_DIRECTORY: str = Field(default="./data/chroma_db")

    # Backend Server
    BACKEND_HOST: str = Field(default="0.0.0.0")
    BACKEND_PORT: int = Field(default=8000)
    SECRET_KEY: str = Field(default="change-me-in-production")
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:5173")

    # Frontend
    VITE_API_BASE_URL: str = Field(default="http://localhost:8000")

    # Simulation
    SIMULATION_INTERVAL_SECONDS: int = Field(default=5)
    SIMULATION_ENABLED: bool = Field(default=True)

    # Anomaly Detection
    ANOMALY_WINDOW_SIZE: int = Field(default=20)
    ANOMALY_ZSCORE_THRESHOLD: float = Field(default=2.5)
    ISOLATION_FOREST_CONTAMINATION: float = Field(default=0.05)

    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: str = Field(default="./logs/safeguard.log")

    # Reports
    REPORTS_OUTPUT_DIR: str = Field(default="./reports")

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def ibm_configured(self) -> bool:
        return bool(self.IBM_WATSONX_API_KEY and self.IBM_WATSONX_PROJECT_ID)

    @property
    def langflow_configured(self) -> bool:
        return bool(self.LANGFLOW_BASE_URL and self.LANGFLOW_FLOW_ID_RAG)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
