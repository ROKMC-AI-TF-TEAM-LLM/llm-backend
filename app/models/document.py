import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class VisibilityEnum(str, enum.Enum):
    ALL = "ALL"              # 전사 공개 (기본)
    DEPT_ONLY = "DEPT_ONLY"  # 소유 부서만


class Document(Base):
    __tablename__ = "documents"

    document_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    # 저장한 사용자. 사용자 삭제 시에도 문서 기록은 유지한다
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    visibility: Mapped[VisibilityEnum] = mapped_column(
        Enum(VisibilityEnum), nullable=False, default=VisibilityEnum.ALL
    )
    content_type: Mapped[str] = mapped_column(
        String(100), nullable=False, default="application/octet-stream"
    )
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    # deferred: 목록 조회 시 원본 바이너리가 로딩되지 않도록 한다
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship()
