from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_server_url: str = "http://localhost:8001"
    request_timeout: int = 60
    max_attachment_size_mb: int = 20
    log_level: str = "INFO"

    database_url: str = "mysql+asyncmy://user:password@localhost:3306/llm_db?charset=utf8mb4"

    jwt_secret_key: str = "change-here"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    model_config = {"env_file": ".env"}


settings = Settings()
