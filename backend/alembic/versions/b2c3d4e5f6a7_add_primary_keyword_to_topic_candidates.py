"""Alembic migration: add primary_keyword to topic_candidates

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'topic_candidates',
        sa.Column('primary_keyword', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('topic_candidates', 'primary_keyword')
