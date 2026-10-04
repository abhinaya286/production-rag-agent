from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str | None = None
    primary_model: str = "gemini-2.5-flash"
    fallback_model: str = "gemini-2.5-pro"
    embedding_model: str = "gemini-embedding-001"

    database_url: str | None = None
    supabase_host: str | None = None
    supabase_port: int = 5432
    supabase_database: str = "postgres"
    supabase_user: str = "postgres"
    supabase_password: str | None = None
    vector_collection_name: str = "production_documents"
    api_access_token: SecretStr | None = None

    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "production-rag"

    app_env: str = "development"
    log_level: str = "INFO"
    rate_limit: str = "20/minute"
    cache_ttl_seconds: int = 300
    max_retries: int = 1
    retrieval_k: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 150

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def vector_database_url(self) -> str | None:
        if self.database_url:
            if self.database_url.startswith("postgres://"):
                return self.database_url.replace(
                    "postgres://", "postgresql+psycopg://", 1
                )
            if self.database_url.startswith("postgresql://"):
                return self.database_url.replace(
                    "postgresql://", "postgresql+psycopg://", 1
                )
            return self.database_url
        if not self.supabase_host or not self.supabase_password:
            return None

        user = quote_plus(self.supabase_user)
        password = quote_plus(self.supabase_password)
        return (
            f"postgresql+psycopg://{user}:{password}@{self.supabase_host}:"
            f"{self.supabase_port}/{self.supabase_database}"
        )

    def validate_rag_configuration(self) -> None:
        missing = []
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if not self.vector_database_url:
            missing.append("DATABASE_URL or SUPABASE_HOST and SUPABASE_PASSWORD")
        if self.is_production and (
            self.api_access_token is None
            or not self.api_access_token.get_secret_value().strip()
        ):
            missing.append("API_ACCESS_TOKEN (required when APP_ENV=production)")
        if self.langsmith_tracing and not self.langsmith_api_key:
            missing.append("LANGSMITH_API_KEY when LANGSMITH_TRACING=true")
        if missing:
            raise ValueError(
                "Missing required RAG configuration: " + ", ".join(missing)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
