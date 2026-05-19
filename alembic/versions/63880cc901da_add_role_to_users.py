"""add role to users

Revision ID: 63880cc901da
Revises: e9f6ca3bfbb0
Create Date: 2026-05-19 14:15:46.904633

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '63880cc901da'
down_revision: Union[str, None] = 'e9f6ca3bfbb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

userrole = sa.Enum('user', 'admin', name='userrole')


def upgrade() -> None:
    userrole.create(op.get_bind())
    op.add_column('users', sa.Column('role', userrole, nullable=False, server_default='user'))


def downgrade() -> None:
    op.drop_column('users', 'role')
    userrole.drop(op.get_bind())
