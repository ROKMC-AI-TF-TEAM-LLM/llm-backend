import logging
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.core.config import settings

LOG_FORMAT = "[%(asctime)s] %(levelname)s [req=%(request_id)s user=%(user_id)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE_NAME = "app.log"

# 요청마다 따로 보관되는 값("요청 메모장"). 미들웨어가 request_id를, 인증 의존성이 user_id를 적고
# 아래 필터가 모든 로그 줄에 붙인다. 요청 밖(서버 기동 등)이나 비로그인 요청은 "-"로 남는다
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


class RequestContextFilter(logging.Filter):
    """로그 줄마다 현재 요청의 request_id·user_id를 채워 넣는다.

    logger가 아니라 handler에 단다 — logger 필터는 자식 logger에서 올라온 줄에는
    적용되지 않아 uvicorn·외부 라이브러리 로그에서 형식 키가 비어 오류가 난다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        return True

# 앱 로그와 같은 곳으로 모을 uvicorn 로거. uvicorn은 기동 시 자기 핸들러를 따로 달아 두므로
# 떼어내고 root로 올려 보낸다 — 남겨 두면 같은 줄이 다른 형식으로 두 번 찍힌다
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

# 기본 INFO에서도 요청마다 한 줄씩 찍는 외부 라이브러리. 앱 로그를 덮지 않도록 WARNING부터만 남긴다
_QUIET_LOGGERS = ("httpx", "httpcore", "watchfiles")


def setup_logging() -> None:
    """서버 시작 시 한 번 호출해 모든 로그를 같은 형식으로 콘솔과 파일에 남긴다.

    출력 장치(handler)는 root에만 단다. 각 모듈의 logger는 기록만 하고
    root로 올려 보내므로(propagate), 형식·저장 위치를 여기 한 곳에서 바꿀 수 있다.
    파일은 자정마다 새로 만들고 log_retention_days개가 넘으면 오래된 것부터 지운다.
    """
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
    context_filter = RequestContextFilter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        log_dir / LOG_FILE_NAME,
        when="midnight",
        backupCount=settings.log_retention_days,
        encoding="utf-8",  # 한국어 Windows 기본값(cp949)이면 파일 속 한글이 깨진다
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    root = logging.getLogger()
    # 두 번 호출돼도(reload 등) 핸들러가 쌓여 줄이 중복되지 않도록 교체한다
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    # 외부 라이브러리 기본 문턱은 WARNING, 우리 코드(app.*)만 설정값을 따른다
    root.setLevel(logging.WARNING)
    logging.getLogger("app").setLevel(settings.log_level.upper())

    for name in _UVICORN_LOGGERS:  #uvicorn 로그를 중앙으로
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    for name in _QUIET_LOGGERS:     #외부 라이브러리 로그를 조용히
        logging.getLogger(name).setLevel(logging.WARNING)

    # uvicorn 접근 로그는 RequestLogMiddleware의 요약 줄(소요 시간·user 포함)이 대신한다. 남겨 두면 요청마다 두 줄
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    # 출력 설정은 setup_logging이 root에 한 번만 한다. 여기서 핸들러를 달면 줄이 두 번 찍힌다
    return logging.getLogger(name)
