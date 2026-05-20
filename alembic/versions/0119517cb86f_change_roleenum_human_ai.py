"""change_roleenum_human_ai

Revision ID: 0119517cb86f
Revises: 63880cc901da
Create Date: 2026-05-20 12:06:12.765339

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0119517cb86f'
down_revision: Union[str, None] = '63880cc901da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tmp = sa.Enum('human', 'ai', name='roleenum_new')
    tmp.create(op.get_bind(), checkfirst=True)

    op.execute("""
        ALTER TABLE messages
        ALTER COLUMN role TYPE roleenum_new
        USING CASE role::text
            WHEN 'user'      THEN 'human'::roleenum_new
            WHEN 'assistant' THEN 'ai'::roleenum_new
            ELSE role::text::roleenum_new
        END
    """)

    op.execute("DROP TYPE IF EXISTS roleenum")
    op.execute("ALTER TYPE roleenum_new RENAME TO roleenum")


def downgrade() -> None:
    tmp = sa.Enum('user', 'assistant', name='roleenum_old')
    tmp.create(op.get_bind(), checkfirst=True)

    op.execute("""
        ALTER TABLE messages
        ALTER COLUMN role TYPE roleenum_old
        USING CASE role::text
            WHEN 'human' THEN 'user'::roleenum_old
            WHEN 'ai'    THEN 'assistant'::roleenum_old
            ELSE role::text::roleenum_old
        END
    """)

    op.execute("DROP TYPE IF EXISTS roleenum")
    op.execute("ALTER TYPE roleenum_old RENAME TO roleenum")
