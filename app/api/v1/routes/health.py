from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse

router = APIRouter(tags=["health"])


@router.get("/database", response_model=ApiResponse[None])
async def check_db(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return ApiResponse.ok()


@router.get("/health", response_model=ApiResponse[None])
async def health():
    return ApiResponse.ok()
