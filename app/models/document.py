import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Timestamp


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
    # NULL이면 전사 문서, 값이 있으면 해당 프로젝트 소유 문서
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True
    )
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    visibility: Mapped[VisibilityEnum] = mapped_column(
        Enum(VisibilityEnum), nullable=False, default=VisibilityEnum.ALL
    )
    content_type: Mapped[str] = mapped_column(
        String(100), nullable=False, default="application/octet-stream"
    )
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    # deferred: 목록 조회 시 원본 바이너리가 로딩되지 않도록 한다
    data: Mapped[bytes] = mapped_column(
        LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=False, deferred=True
    )
    # 상태 저장: MARS가 주는 값(queued/running/done/error 등)을 번역 없이 그대로 저장한다.
    # relay 전 로컬 초기값은 "pending".
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chunks_indexed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        Timestamp,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    #최근 갱신 시점 표시.
    updated_at: Mapped[datetime] = mapped_column( 
        Timestamp,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),  # 행 바뀔 때마다 자동 갱신
        nullable=False,
    )

    user: Mapped["User"] = relationship()
    project: Mapped["Project | None"] = relationship(back_populates="documents")
