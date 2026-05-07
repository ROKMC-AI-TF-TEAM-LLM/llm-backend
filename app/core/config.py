from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_server_url: str = "http://localhost:8001"
    request_timeout: int = 60

    model_config = {"env_file": ".env"}


settings = Settings()
