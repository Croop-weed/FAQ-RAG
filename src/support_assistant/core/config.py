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

    # Hugging Face Configuration
    hf_api_key: str = ""
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    llm_provider: str = "not-configured"
    llm_model: str = "not-configured"


    # Azure AI Search Configuration
    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index: str = "faq-index"

    # Legacy & Runtime Parameters
    ollama_host: str = "http://localhost:11434"
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    generation_evidence_top_k: int = Field(default=5, ge=1, le=10)
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    evaluation_top_k: int = Field(default=5, ge=5)
    embedding_cache_dir: Path = Path("models/cache/embeddings")
    bm25_top_k: int = Field(default=20, ge=1)
    vector_top_k: int = Field(default=20, ge=1)
    fusion_top_k: int = Field(default=20, ge=1)
    rrf_k: int = Field(default=60, ge=1)
    rerank_top_k: int = Field(default=5, ge=1)
    confidence_accept_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    confidence_review_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    min_evidence_reranker_score: float = Field(default=0.30)
    min_supporting_evidence_count: int = Field(default=1, ge=1)
    knowledge_gap_threshold: float = Field(default=0.25)

