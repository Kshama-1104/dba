"""Alembic migration: create topic_candidates table

Revision ID: a1b2c3d4e5f6
Revises: 8ddb1c9bbb73
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8ddb1c9bbb73'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'topic_candidates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('angle', sa.Text(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('target_audience', sa.String(length=255), nullable=True),
        sa.Column('source_context', sa.Text(), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('freshness_score', sa.Float(), nullable=True),
        sa.Column('status', sa.Enum('suggested', 'selected', 'rejected', 'used', 'expired', name='topicstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_topic_candidates_company_id'), 'topic_candidates', ['company_id'], unique=False)
    op.create_index(op.f('ix_topic_candidates_created_by'), 'topic_candidates', ['created_by'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_topic_candidates_created_by'), table_name='topic_candidates')
    op.drop_index(op.f('ix_topic_candidates_company_id'), table_name='topic_candidates')
    op.drop_table('topic_candidates')
    sa.Enum(name='topicstatus').drop(op.get_bind(), checkfirst=True)
