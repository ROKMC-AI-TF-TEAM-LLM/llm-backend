import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, Text, String
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Timestamp


class RoleEnum(str, enum.Enum):
    human = "human"
    ai = "ai"


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=True)
    # SSE notice 이벤트의 code (NULL이면 경고 없음). 저장하지 않으면 세션 재진입 시
    # 경고가 사라져, 근거 검증을 거치지 않은 답변이 평범한 답변으로 보인다
    notice_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    content: Mapped[str] = mapped_column(
        Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        Timestamp,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    session: Mapped["Session"] = relationship(back_populates="messages")
    sources: Mapped[list["Source"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
