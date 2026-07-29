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


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
