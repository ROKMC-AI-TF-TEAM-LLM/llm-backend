from sqlalchemy import DateTime
from sqlalchemy.dialects.mysql import DATETIME as MYSQL_DATETIME
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    # MySQL은 wait_timeout(기본 8시간)이 지난 유휴 커넥션을 서버가 끊는다.
    # 풀에 남은 죽은 커넥션을 잡으면 "MySQL server has gone away"가 나므로,
    # 1시간마다 커넥션을 갈아끼우고(recycle) 대여 직전 생존 확인(pre_ping)까지 건다.
    pool_recycle=3600,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# MySQL의 DATETIME은 소수점 이하 초 자릿수(fsp)를 안 붙이면 0자리라 마이크로초가 잘린다.
# 커서 페이지네이션이 created_at을 커서로 쓰고 조건이 `created_at < cursor`(등호 없음)라,
# 같은 초에 저장된 행들이 동점이 되면 페이지 경계에서 통째로 누락된다.
# PostgreSQL(TIMESTAMPTZ, 마이크로초)과 정밀도를 맞추기 위해 MySQL에서만 fsp=6을 명시한다.
Timestamp = DateTime(timezone=True).with_variant(MYSQL_DATETIME(fsp=6), "mysql")


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
