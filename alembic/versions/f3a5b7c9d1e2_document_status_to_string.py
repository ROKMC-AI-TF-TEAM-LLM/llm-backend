"""document status enum to string

Revision ID: f3a5b7c9d1e2
Revises: e2b4c6d8f0a1
Create Date: 2026-07-23 15:00:00.000000

MARS가 주는 상태 값을 번역 없이 그대로 저장하기 위해
documents.status 컬럼을 indexstatusenum → VARCHAR(20)으로 변경한다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f3a5b7c9d1e2'
down_revision: Union[str, None] = 'e2b4c6d8f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

indexstatusenum = sa.Enum('PENDING', 'INDEXING', 'INDEXED', 'FAILED', name='indexstatusenum')


def upgrade() -> None:
    # 1. enum 기본값 제거 (타입 변경 전에 떼야 함)
    op.alter_column('documents', 'status', server_default=None)

    # 2. enum → varchar 로 타입 변경
    op.alter_column(
        'documents',
        'status',
        type_=sa.String(20),
        existing_nullable=False,
        postgresql_using='status::text',
    )

    # 3. 기존 대문자 값을 새 소문자 raw 값으로 매핑
    op.execute("UPDATE documents SET status = 'pending' WHERE status = 'PENDING'")
    op.execute("UPDATE documents SET status = 'running' WHERE status = 'INDEXING'")
    op.execute("UPDATE documents SET status = 'done'    WHERE status = 'INDEXED'")
    op.execute("UPDATE documents SET status = 'error'   WHERE status = 'FAILED'")

    # 4. 새 기본값 설정
    op.alter_column('documents', 'status', server_default='pending')

    # 5. 더 이상 쓰지 않는 enum 타입 제거
    indexstatusenum.drop(op.get_bind())


def downgrade() -> None:
    # 1. enum 타입 재생성
    indexstatusenum.create(op.get_bind())

    # 2. 소문자 raw 값을 다시 대문자 enum 값으로 매핑
    op.execute("UPDATE documents SET status = 'PENDING'  WHERE status = 'pending'")
    op.execute("UPDATE documents SET status = 'INDEXING' WHERE status IN ('queued', 'running')")
    op.execute("UPDATE documents SET status = 'INDEXED'  WHERE status = 'done'")
    op.execute("UPDATE documents SET status = 'FAILED'   WHERE status = 'error'")

    # 3. 기본값 제거 후 varchar → enum 타입 변경
    op.alter_column('documents', 'status', server_default=None)
    op.alter_column(
        'documents',
        'status',
        type_=indexstatusenum,
        existing_nullable=False,
        postgresql_using='status::indexstatusenum',
    )
    op.alter_column('documents', 'status', server_default='PENDING')
