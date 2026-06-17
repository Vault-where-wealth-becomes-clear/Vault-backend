from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket_name: str = "vault-beta"
    sqs_queue_url: str = ""
    sqs_dlq_url: str = ""

    # Cognito
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"

    # Database
    database_url: str = "postgresql+asyncpg://vault:password@localhost:5432/vault"

    # LLM
    llm_model: str = "claude-3-5-haiku-20241022"
    anthropic_api_key: str = ""

    # App
    environment: str = "development"
    confidence_threshold: float = 0.75
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]
    app_version: str = "0.1.0"


settings = Settings()
