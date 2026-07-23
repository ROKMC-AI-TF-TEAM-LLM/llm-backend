"""add_index_status_to_documents

Revision ID: d1a2b3c4e5f6
Revises: c4d8e6f1a2b3
Create Date: 2026-07-22 11:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd1a2b3c4e5f6'
down_revision: Union[str, None] = 'c4d8e6f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

indexstatusenum = sa.Enum('PENDING', 'INDEXING', 'INDEXED', 'FAILED', name='indexstatusenum')


def upgrade() -> None:
    indexstatusenum.create(op.get_bind())
    op.add_column(
        'documents',
        sa.Column('status', indexstatusenum, nullable=False, server_default='PENDING'),
    )
    op.add_column('documents', sa.Column('job_id', sa.String(64), nullable=True))
    op.add_column('documents', sa.Column('chunks_indexed', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('error', sa.Text(), nullable=True))
    op.add_column(
        'documents',
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column('documents', 'updated_at')
    op.drop_column('documents', 'error')
    op.drop_column('documents', 'chunks_indexed')
    op.drop_column('documents', 'job_id')
    op.drop_column('documents', 'status')
    indexstatusenum.drop(op.get_bind())
