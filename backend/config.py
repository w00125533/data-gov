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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
