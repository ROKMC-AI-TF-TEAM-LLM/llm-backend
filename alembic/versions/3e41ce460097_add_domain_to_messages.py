"""add_domain_to_messages

Revision ID: 3e41ce460097
Revises: f3a5b7c9d1e2
Create Date: 2026-07-24 22:17:25.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '3e41ce460097'
down_revision: Union[str, None] = 'f3a5b7c9d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('domain', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'domain')
