from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services.health_service import check_db, check_llm_server, check_translation_server

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    db: bool
    llm_server: bool
    translate_server: bool


@router.get(
    "/health",
    response_model=ApiResponse[HealthResponse],
    summary="서버 상태 확인",
    description="DB 연결 상태와 LLM 서버·번역 서버 연결 상태를 반환합니다.",
)
async def health(db: AsyncSession = Depends(get_db)):
    db_ok = await check_db(db)
    llm_ok = await check_llm_server()
    translate_ok = await check_translation_server()
    return ApiResponse.ok(
        HealthResponse(db=db_ok, llm_server=llm_ok, translate_server=translate_ok), status_code=200
    )
