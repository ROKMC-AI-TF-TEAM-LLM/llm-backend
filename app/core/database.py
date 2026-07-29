from datetime import datetime, timezone

from sqlalchemy import DateTime, TypeDecorator
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


class UtcDateTime(TypeDecorator):
    """항상 UTC로 저장하고 항상 UTC로 읽어오는 타임스탬프 타입.

    MySQL로 옮기면서 생긴 두 가지 차이를 함께 흡수한다.

    1) 정밀도
       MySQL의 DATETIME은 소수점 이하 초 자릿수(fsp)를 명시하지 않으면 0자리라
       마이크로초가 잘린다. 커서 페이지네이션이 created_at을 커서로 쓰고 조건이
       `created_at < cursor`(등호 없음)이므로, 값이 뭉개져 동점이 생기면 페이지
       경계에서 행이 통째로 누락된다. → MySQL에서만 fsp=6을 지정한다.

    2) 시간대
       PostgreSQL의 TIMESTAMPTZ는 시간대를 보존하지만 MySQL의 DATETIME은 보존하지
       못한다. 그대로 두면 읽어올 때 tzinfo가 없는 naive datetime이 되고, API 응답이
       '2026-07-29T10:00:00'처럼 오프셋 없이 나간다. 자바스크립트는 오프셋 없는
       날짜+시각 문자열을 '로컬 시간'으로 해석하므로 화면에서 9시간 어긋난다.
       → 쓸 때 UTC로 변환하고, 읽을 때 tzinfo=UTC를 다시 붙여 기존 응답 형식을 지킨다.

    이 타입은 DATETIME(6)을 감싸기만 하므로 DDL이 바뀌지 않는다. 즉 마이그레이션이
    필요 없다.
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(MYSQL_DATETIME(fsp=6))
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        # tzinfo가 없는 값은 UTC로 간주한다 (앱은 항상 datetime.now(timezone.utc)를 쓴다)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        if dialect.name == "mysql":
            # DATETIME은 시간대를 저장하지 않으므로 UTC 벽시계 값만 넘긴다
            return value.replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        # MySQL에서 돌아온 값은 tzinfo가 없다. 저장 시 UTC로 맞췄으므로 UTC를 붙여준다.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


Timestamp = UtcDateTime()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
