from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import admin, auth, document, health, message, session, user
from app.core.exceptions import AppHTTPException
from app.core.logger import get_logger
from app.schemas.common import ApiResponse
from app.services.health_service import check_llm_server

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.core.database import AsyncSessionLocal, engine
    from app.services.health_service import check_db

    async with AsyncSessionLocal() as db:
        db_ok = await check_db(db)
    logger.info("DB 연결 확인 완료") if db_ok else logger.warning("DB에 연결할 수 없습니다")

    llm_ok = await check_llm_server()
    logger.info("LLM 서버 연결 확인 완료") if llm_ok else None
    yield

    await engine.dispose()
    logger.info("DB 커넥션 풀 정리 완료")


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
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.fail(code=exc.error_code, detail=exc.detail, status_code=exc.status_code).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    detail = "; ".join(
        f"{' -> '.join(str(l) for l in e['loc'])}: {e['msg']}" for e in exc.errors()
    )
    return JSONResponse(
        status_code=422,
        content=ApiResponse.fail(code="VALIDATION_ERROR", detail=detail, status_code=422).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.fail(code="HTTP_ERROR", detail=exc.detail, status_code=exc.status_code).model_dump(),
    )


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1")
app.include_router(message.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(document.router, prefix="/api/v1")
