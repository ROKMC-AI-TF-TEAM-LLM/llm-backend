from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_server_url: str = "http://localhost:8001"
    request_timeout: int = 60
    max_attachment_size_mb: int = 20
    # AI 서버(MARS) 상한과 동일하게 맞춰 여기서 먼저 거부한다 (안 그러면 거부될 파일이 DB에 저장된 뒤 버려짐)
    max_document_size_mb: int = 50
    log_level: str = "INFO"

    # 군사 도메인 한↔영 번역 서버(NeuroDomain-Translate). 채팅용 AI 서버와 별개 프로세스다.
    translate_server_url: str = "http://localhost:9001"
    # 번역 서버는 원문을 청크로 쪼개 모델을 여러 번 부른다(청크당 상한 180초).
    # request_timeout(60초)을 그대로 쓰면 서버가 아직 번역 중인데 프록시가 먼저 끊는다.
    translate_timeout: int = 300

    database_url: str = "mysql+asyncmy://user:password@localhost:3306/llm_db?charset=utf8mb4"

    jwt_secret_key: str = "change-here"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    model_config = {"env_file": ".env"}


settings = Settings()
