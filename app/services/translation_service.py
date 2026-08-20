import httpx

from app.core.config import settings
from app.core.exceptions import TextTooLongError, TranslateServerError
from app.core.logger import get_logger
from app.schemas.translation import TranslateRequest

logger = get_logger(__name__)


def _upstream_detail(response: httpx.Response, fallback: str) -> str:
    """번역 서버는 FastAPI 기본 형식({"detail": "..."})으로 오류 사유를 준다."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        return fallback
    return detail if isinstance(detail, str) and detail else fallback


async def translate(req: TranslateRequest) -> dict:
    url = f"{settings.translate_server_url}/translate"
    # 번역 서버 요청 모델이 extra="forbid"라 정의되지 않은 키를 보내면 422가 난다.
    # style은 아예 빼야 서버 기본값(press_release)이 적용되므로 값이 있을 때만 싣는다.
    payload: dict = {"text": req.text, "source": req.source, "target": req.target}
    if req.style:
        payload["style"] = req.style

    try:
        async with httpx.AsyncClient(timeout=settings.translate_timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        logger.error("번역 실패 status=%d url=%s", status, url)
        # 길이 상한은 번역 서버(NDT_MAX_INPUT_CHARS)가 단일 출처다.
        # 여기서 같은 규칙을 다시 두면 상한이 두 곳이 되므로 사유 문구만 그대로 옮긴다.
        if status == 413:
            raise TextTooLongError(detail=_upstream_detail(e.response, TextTooLongError.detail))
        raise TranslateServerError(detail=f"번역 서버 오류: HTTP {status}")
    except httpx.TimeoutException:
        logger.error("번역 서버 응답 시간 초과 url=%s timeout=%d초", url, settings.translate_timeout)
        raise TranslateServerError(detail="번역 서버 응답 시간이 초과되었습니다.")
    except httpx.RequestError:
        logger.error("번역 서버 연결 오류 url=%s", url)
        raise TranslateServerError(detail="번역 서버에 연결할 수 없습니다.")
    except Exception:
        logger.exception("번역 응답 처리 실패 url=%s", url)
        raise TranslateServerError()
