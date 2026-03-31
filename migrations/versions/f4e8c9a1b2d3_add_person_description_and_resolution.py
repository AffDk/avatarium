"""add_person_description_and_project_resolution

Revision ID: f4e8c9a1b2d3
Revises: c3a1f9b2e4d7
Create Date: 2026-03-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4e8c9a1b2d3'
down_revision: Union[str, None] = 'c3a1f9b2e4d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('persons', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('video_resolution', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'video_resolution')
    op.drop_column('persons', 'description')
