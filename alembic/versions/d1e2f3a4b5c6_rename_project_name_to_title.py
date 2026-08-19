"""rename projects.name to title

Revision ID: d1e2f3a4b5c6
Revises: c8a2d3e4f5b6
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c8a2d3e4f5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'projects', 'name',
        new_column_name='title',
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'projects', 'title',
        new_column_name='name',
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
