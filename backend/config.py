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

    # Agent (slice 2b)
    agent_max_iterations: int = Field(3, alias="AGENT_MAX_ITERATIONS")
    git_author_name: str = Field("Data-Gov Agent", alias="GIT_AUTHOR_NAME")
    git_author_email: str = Field("agent@data-gov.local", alias="GIT_AUTHOR_EMAIL")

    # Sandbox (slice 2c)
    sandbox_base_dir: str = Field("/tmp/sandbox", alias="SANDBOX_BASE_DIR")
    sandbox_hdfs_base: str = Field("/tmp/sandbox", alias="SANDBOX_HDFS_BASE")
    sandbox_total_timeout: int = Field(60, alias="SANDBOX_TOTAL_TIMEOUT")
    sandbox_compile_timeout: int = Field(20, alias="SANDBOX_COMPILE_TIMEOUT")
    sandbox_spark_timeout: int = Field(30, alias="SANDBOX_SPARK_TIMEOUT")
    sandbox_flink_timeout: int = Field(45, alias="SANDBOX_FLINK_TIMEOUT")
    sandbox_max_retries: int = Field(2, alias="SANDBOX_MAX_RETRIES")
    yarn_rm_url: str = Field("http://resourcemanager:8088", alias="YARN_RM_URL")
    hdfs_defaultfs: str = Field("hdfs://namenode:8020", alias="HDFS_DEFAULTFS")
    hive_metastore_uri: str = Field("thrift://hive-metastore:9083", alias="HIVE_METASTORE_URI")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
