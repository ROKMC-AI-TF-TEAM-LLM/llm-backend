"""add_approval_status_to_users

Revision ID: 5f69628aa33d
Revises: 0119517cb86f
Create Date: 2026-05-21 08:40:57.945390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5f69628aa33d'
down_revision: Union[str, None] = '0119517cb86f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    approvalstatus = sa.Enum('pending', 'approved', 'rejected', name='approvalstatus')
    approvalstatus.create(op.get_bind(), checkfirst=True)
    op.add_column('users', sa.Column('status', approvalstatus, nullable=False, server_default='pending'))


def downgrade() -> None:
    op.drop_column('users', 'status')
    sa.Enum(name='approvalstatus').drop(op.get_bind(), checkfirst=True)
