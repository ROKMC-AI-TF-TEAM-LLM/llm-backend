"""add_is_favorite_to_sessions

Revision ID: a8c1d4e7f2b9
Revises: 3c7d2e1f4a8b
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a8c1d4e7f2b9'
down_revision: Union[str, None] = '3c7d2e1f4a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'sessions',
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('sessions', 'is_favorite')
