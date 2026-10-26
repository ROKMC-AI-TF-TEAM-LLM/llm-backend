import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logger import get_logger, request_id_var

logger = get_logger("app.request")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestLogMiddleware:
    """요청마다 request_id를 발급하고, 응답이 끝나면 요약 한 줄을 남긴다.

    BaseHTTPMiddleware가 아닌 순수 ASGI로 만든다 — BaseHTTPMiddleware는 응답 헤더가
    나가는 순간 끝난 것으로 보므로, 수십 초짜리 채팅 스트리밍이 0.x초로 찍힌다.
    여기서는 self.app 호출이 본문 전송까지 다 끝나야 돌아오므로 실제 소요 시간이 남는다.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:8]
        # reset하지 않는다. uvicorn은 요청마다 별도 task(=별도 컨텍스트)에서 실행하므로 다른 요청으로
        # 새지 않고, 처리되지 않은 예외의 traceback(uvicorn.error)에도 같은 request_id가 남는다
        request_id_var.set(request_id)

        method = scope["method"]
        path = scope["path"]
        client = scope.get("client")
        client_ip = client[0] if client else "-"
        status_code = 500  # 응답을 시작하지 못하고 예외로 끝나면 500으로 남긴다
        started = time.perf_counter()
        logger.debug("요청 시작 %s %s ip=%s", method, path, client_ip)

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # 사용자가 오류를 문의할 때 이 값을 알려주면 해당 요청의 로그를 바로 찾을 수 있다
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            elapsed = time.perf_counter() - started
            log = logger.warning if status_code >= 500 else logger.info
            log("%s %s %d %.2fs ip=%s", method, path, status_code, elapsed, client_ip)
