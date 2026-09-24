from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # LLM Provider Configuration
    llm_provider: str = "deterministic"
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None

    # Integration Credential Vault Secret (Optional override, defaults to jwt_secret_key)
    integration_secret_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()