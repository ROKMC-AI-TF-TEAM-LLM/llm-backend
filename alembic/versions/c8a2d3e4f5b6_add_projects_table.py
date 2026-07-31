"""add_projects_table

Revision ID: c8a2d3e4f5b6
Revises: 3e41ce460097
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c8a2d3e4f5b6'
down_revision: Union[str, None] = '3e41ce460097'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'projects',
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('project_id'),
    )

    op.add_column('sessions', sa.Column('project_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_sessions_project_id', 'sessions', 'projects',
        ['project_id'], ['project_id'], ondelete='CASCADE',
    )

    op.add_column('documents', sa.Column('project_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_documents_project_id', 'documents', 'projects',
        ['project_id'], ['project_id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('fk_documents_project_id', 'documents', type_='foreignkey')
    op.drop_column('documents', 'project_id')

    op.drop_constraint('fk_sessions_project_id', 'sessions', type_='foreignkey')
    op.drop_column('sessions', 'project_id')

    op.drop_table('projects')
