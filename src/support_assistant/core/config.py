from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SUPPORT_ASSISTANT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "customer-support-assistant"
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./data/support_assistant.db"
    llm_provider: str = "not-configured"
    llm_model: str = "not-configured"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "not-configured"
    evaluation_top_k: int = Field(default=5, ge=5)
    embedding_cache_dir: Path = Path("models/cache/embeddings")
    bm25_top_k: int = Field(default=20, ge=1)
    vector_top_k: int = Field(default=20, ge=1)
    rerank_top_k: int = Field(default=5, ge=1)
