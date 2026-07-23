"""make_department_nullable

Revision ID: e2b4c6d8f0a1
Revises: d1a2b3c4e5f6
Create Date: 2026-07-23 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e2b4c6d8f0a1'
down_revision: Union[str, None] = 'd1a2b3c4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'documents',
        'department',
        existing_type=sa.String(100),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'documents',
        'department',
        existing_type=sa.String(100),
        nullable=False,
    )
