"""add_attachments_table

Revision ID: b9f3a1c5d7e2
Revises: a8c1d4e7f2b9
Create Date: 2026-07-20 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b9f3a1c5d7e2'
down_revision: Union[str, None] = 'a8c1d4e7f2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'attachments',
        sa.Column('attachment_id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.message_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('attachment_id'),
    )
    op.create_index('ix_attachments_message_id', 'attachments', ['message_id'])


def downgrade() -> None:
    op.drop_index('ix_attachments_message_id', table_name='attachments')
    op.drop_table('attachments')
