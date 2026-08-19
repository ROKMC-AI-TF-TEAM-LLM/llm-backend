from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_server_url: str = "http://localhost:8001"
    request_timeout: int = 60
    max_attachment_size_mb: int = 20
    # 업로드 문서 크기 상한. AI 서버(MARS)의 상한과 같은 값으로 맞춘다 —
    # 여기서 먼저 막지 않으면 거부될 파일이 DB에 통째로 저장된 뒤에 버려진다
    max_document_size_mb: int = 50
    log_level: str = "INFO"

    database_url: str = "mysql+asyncmy://user:password@localhost:3306/llm_db?charset=utf8mb4"

    jwt_secret_key: str = "change-here"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    model_config = {"env_file": ".env"}


settings = Settings()
