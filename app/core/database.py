from datetime import datetime, timezone

from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.engine import make_url
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

_url = make_url(settings.database_url)

_connect_args: dict = {}
if settings.db_disable_ssl and _url.get_driver_name() == "asyncpg":
    _connect_args["ssl"] = False

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_recycle=3600,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


class UtcDateTime(TypeDecorator):
    """항상 UTC aware datetime 을 주고받는 DateTime (MySQL 은 DATETIME(6))."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> DateTime:
        if dialect.name == "mysql":
            return dialect.type_descriptor(DATETIME(fsp=6))
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        if dialect.name == "mysql":
            return value.replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


Timestamp = UtcDateTime()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
