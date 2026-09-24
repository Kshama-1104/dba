"""Alembic migration: create external_integrations and company_social_insights tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))

    # 1. external_integrations table
    op.create_table(
        'external_integrations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'),
        sa.Column('credentials_encrypted', sa.Text(), nullable=False),
        sa.Column('sync_status', sa.String(length=50), nullable=False, server_default='IDLE'),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('sync_error', sa.Text(), nullable=True),
        sa.Column('metadata_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'platform', name='uq_company_platform'),
    )
    op.create_index(
        'ix_external_integrations_company_id',
        'external_integrations',
        ['company_id'],
        unique=False,
    )
    op.create_index(
        'ix_external_integrations_tenant_status',
        'external_integrations',
        ['company_id', 'status'],
        unique=False,
    )

    # 2. company_social_insights table
    op.create_table(
        'company_social_insights',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('integration_id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('source_url', sa.String(length=1000), nullable=True),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('freshness_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('metadata_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['integration_id'], ['external_integrations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'platform', 'external_id', name='uq_tenant_platform_external_id'),
    )
    op.create_index(
        'ix_company_social_insights_company_id',
        'company_social_insights',
        ['company_id'],
        unique=False,
    )
    op.create_index(
        'ix_company_social_insights_integration_id',
        'company_social_insights',
        ['integration_id'],
        unique=False,
    )
    op.create_index(
        'ix_company_social_insights_tenant_date',
        'company_social_insights',
        ['company_id', 'published_at'],
        unique=False,
    )
    op.create_index(
        'ix_company_social_insights_tenant_hash',
        'company_social_insights',
        ['company_id', 'content_hash'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table('company_social_insights')
    op.drop_table('external_integrations')
