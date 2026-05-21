from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import admin, auth, health, message, session, user
from app.core.config import settings
from app.core.exceptions import AppHTTPException
from app.core.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await _check_llm_server()
    yield


async def _check_llm_server():
    url = f"{settings.llm_server_url}/api/health"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
            response.raise_for_status()
        logger.info("LLM 서버 연결 확인 완료 (%s)", url)
    except httpx.HTTPStatusError as e:
        logger.warning("LLM 서버 응답 오류 status=%d url=%s", e.response.status_code, url)
    except Exception:
        logger.warning("LLM 서버에 연결할 수 없습니다 url=%s", url)


app = FastAPI(title="LLM Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.exception_handler(AppHTTPException)
async def app_http_exception_handler(_request: Request, exc: AppHTTPException):
    from app.schemas.common import ApiResponse
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.fail(code=exc.error_code, detail=exc.detail, status_code=exc.status_code).model_dump(),
    )


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1")
app.include_router(message.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
