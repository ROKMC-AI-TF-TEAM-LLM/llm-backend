"""add_documents_table

Revision ID: c4d8e6f1a2b3
Revises: b9f3a1c5d7e2
Create Date: 2026-07-22 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c4d8e6f1a2b3'
down_revision: Union[str, None] = 'b9f3a1c5d7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'documents',
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('domain', sa.String(50), nullable=False),
        sa.Column('department', sa.String(100), nullable=False),
        sa.Column(
            'visibility',
            sa.Enum('ALL', 'DEPT_ONLY', name='visibilityenum'),
            nullable=False,
            server_default='ALL',
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('document_id'),
    )
    op.create_index('ix_documents_user_id', 'documents', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_documents_user_id', table_name='documents')
    op.drop_table('documents')
    sa.Enum(name='visibilityenum').drop(op.get_bind(), checkfirst=True)
