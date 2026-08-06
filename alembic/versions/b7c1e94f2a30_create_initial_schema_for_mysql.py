"""create initial schema for mysql

Revision ID: b7c1e94f2a30
Revises:
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = 'b7c1e94f2a30'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), 'mysql')


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.Enum('user', 'admin', name='userrole'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='approvalstatus'), nullable=False),
        sa.Column('refresh_token', sa.String(length=512), nullable=True),
        sa.Column('created_at', _TS, nullable=False),
        sa.Column('updated_at', _TS, nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email'),
    )
    op.create_table(
        'sessions',
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('created_at', _TS, nullable=False),
        sa.Column('updated_at', _TS, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('session_id'),
    )
    op.create_table(
        'messages',
        sa.Column('message_id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.Enum('human', 'ai', name='roleenum'), nullable=False),
        sa.Column('content', sa.Text().with_variant(mysql.MEDIUMTEXT(), 'mysql'), nullable=False),
        sa.Column('created_at', _TS, nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.session_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('message_id'),
    )
    op.create_table(
        'sources',
        sa.Column('source_id', sa.Uuid(), nullable=False),
        sa.Column('message_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('page', sa.String(length=50), nullable=True),
        sa.Column('created_at', _TS, nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.message_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('source_id'),
    )
    op.create_index('ix_sources_message_id', 'sources', ['message_id'])


def downgrade() -> None:
    op.drop_index('ix_sources_message_id', table_name='sources')
    op.drop_table('sources')
    op.drop_table('messages')
    op.drop_table('sessions')
    op.drop_table('users')
