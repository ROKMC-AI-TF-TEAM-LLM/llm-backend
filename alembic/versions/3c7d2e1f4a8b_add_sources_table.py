"""add_sources_table

Revision ID: 3c7d2e1f4a8b
Revises: f6d6325672ec
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '3c7d2e1f4a8b'
down_revision: Union[str, None] = 'f6d6325672ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sources',
        sa.Column('source_id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('page', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.message_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('source_id'),
    )
    op.create_index('ix_sources_message_id', 'sources', ['message_id'])


def downgrade() -> None:
    op.drop_index('ix_sources_message_id', table_name='sources')
    op.drop_table('sources')
