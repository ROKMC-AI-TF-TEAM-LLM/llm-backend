import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Timestamp


class Source(Base):
    __tablename__ = "sources"

    source_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.message_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    # MARS가 출처로 준 원본 문서 id. 필드 도입 전 답변과 id 없는 출처는 NULL.
    # FK는 걸지 않는다 — DB에 없는 id가 오면 답변 저장 전체가 실패하기 때문이다
    document_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    page: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        Timestamp,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    message: Mapped["Message"] = relationship(back_populates="sources")
