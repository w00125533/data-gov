"""Application settings loaded from environment / .env."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    neo4j_uri: str = Field("bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field("neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field("data-gov-neo4j", alias="NEO4J_PASSWORD")
    neo4j_database: str = Field("neo4j", alias="NEO4J_DATABASE")

    metadata_yaml_dir: str = Field("metadata-yaml", alias="METADATA_YAML_DIR")

    # DeepSeek (slice 2a rerank + slice 2b LangGraph nodes)
    deepseek_api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field("https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field("deepseek-chat", alias="DEEPSEEK_MODEL")

    # Semantic search (slice 2a)
    search_chroma_dir: str = Field("./data/chroma", alias="SEARCH_CHROMA_DIR")
    search_embed_model: str = Field("BAAI/bge-small-zh-v1.5", alias="SEARCH_EMBED_MODEL")
    search_rerank_threshold: float = Field(0.15, alias="SEARCH_RERANK_THRESHOLD")
    search_rrf_k: int = Field(60, alias="SEARCH_RRF_K")
    search_bootstrap_from_seed: bool = Field(False, alias="SEARCH_BOOTSTRAP_FROM_SEED")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
