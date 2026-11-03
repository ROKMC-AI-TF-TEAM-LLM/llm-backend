"""add current_sid to users

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 기존 행은 NULL로 남는다 — sid 없는 옛 토큰은 거절되므로 배포 후 모든 사용자가 한 번 다시 로그인한다
    op.add_column(
        'users',
        sa.Column('current_sid', sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'current_sid')
