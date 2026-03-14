"""add_persons_column_to_segments

Revision ID: c3a1f9b2e4d7
Revises: 8df2d3f8096a
Create Date: 2026-03-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a1f9b2e4d7'
down_revision: Union[str, None] = '8df2d3f8096a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('segments', sa.Column('persons', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('segments', 'persons')
