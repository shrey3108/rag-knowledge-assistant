from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Ollama Cloud / API Configuration
    ollama_url: str = Field(default="https://ollama.com/", alias="OLLAMA_URL")
    ollama_api_key: str = Field(default="", alias="OLLAMA_API_KEY")
    ollama_model: str = Field(default="gpt-oss:120b-cloud", alias="OLLAMA_MODEL")
    ollama_timeout_seconds: float = Field(default=90.0, alias="OLLAMA_TIMEOUT_SECONDS")

    # Embeddings & Vector Database
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL")
    chroma_persist_directory: str = Field(default="./data/chroma_db", alias="CHROMA_PERSIST_DIRECTORY")
    collection_name: str = Field(default="knowledge_base", alias="COLLECTION_NAME")

    # Chunking & RAG Retrieval
    top_k: int = Field(default=4, alias="TOP_K")
    similarity_threshold: float = Field(default=0.35, alias="SIMILARITY_THRESHOLD")
    max_chunk_size: int = Field(default=650, alias="MAX_CHUNK_SIZE")
    chunk_overlap: int = Field(default=100, alias="CHUNK_OVERLAP")

    # Server settings
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Redis Cache Configuration
    redis_enabled: bool = Field(default=True, alias="REDIS_ENABLED")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    redis_ttl_seconds: int = Field(default=3600, alias="REDIS_TTL_SECONDS")

    # Offline / Mock mode for automated testing without live API network calls
    mock_llm: bool = Field(default=False, alias="MOCK_LLM")


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def chat_completions_url(self) -> str:
        """Construct the /v1/chat/completions endpoint as requested."""
        base = self.ollama_url.strip().rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
