"""add document_id to sources

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-10-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 기존 행은 NULL로 남는다 — 이름만으로는 같은 이름의 문서 중 어느 것인지
    # 확정할 수 없어 백필하지 않는다
    op.add_column(
        'sources',
        sa.Column('document_id', sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('sources', 'document_id')
