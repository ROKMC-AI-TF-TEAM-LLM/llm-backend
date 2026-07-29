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
    # MySQL의 TEXT는 65,535바이트(utf8mb4 한글 약 2만자)라 LLM 답변에 부족할 수 있어
    # MEDIUMTEXT(16MB)로 올린다
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
