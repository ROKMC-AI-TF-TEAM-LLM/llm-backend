"""add notice_code to messages

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-08-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 기존 행은 NULL로 남는다 — AI 서버에 경고(notice) 경로가 생기기 전 답변들이라
    # "경고 없음"이 사실과 일치한다. 백필 불필요
    op.add_column(
        'messages',
        sa.Column('notice_code', sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('messages', 'notice_code')
