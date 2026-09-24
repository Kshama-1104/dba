"""Alembic migration: add wordpress publishing (Phase 11)

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h8c9d0e1f2a3'
down_revision = 'g7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Create wordpress_connections table
    if 'wordpress_connections' not in tables:
        op.create_table(
            'wordpress_connections',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('site_url', sa.String(length=500), nullable=False),
            sa.Column('username', sa.String(length=255), nullable=False),
            sa.Column('encrypted_credential', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='ACTIVE'),
            sa.Column('default_post_status', sa.String(length=32), nullable=False, server_default='publish'),
            sa.Column('created_by_user_id', sa.Integer(), nullable=False),
            sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
            sa.UniqueConstraint('company_id', name='uq_company_wordpress_connection'),
        )
        op.create_index('ix_wordpress_connections_id', 'wordpress_connections', ['id'], unique=False)
        op.create_index('ix_wordpress_connections_company_id', 'wordpress_connections', ['company_id'], unique=False)

    # 2. Create wordpress_publication_records table
    if 'wordpress_publication_records' not in tables:
        op.create_table(
            'wordpress_publication_records',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('connection_id', sa.Integer(), nullable=True),
            sa.Column('schedule_id', sa.Integer(), nullable=True),
            sa.Column('last_job_id', sa.Integer(), nullable=True),
            sa.Column('blog_id', sa.Integer(), nullable=False),
            sa.Column('revision_id', sa.Integer(), nullable=False),
            sa.Column('publication_idempotency_key', sa.String(length=128), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='IN_PROGRESS'),
            sa.Column('claim_worker_id', sa.String(length=128), nullable=True),
            sa.Column('claim_lease_until', sa.DateTime(timezone=True), nullable=True),
            sa.Column('external_post_id', sa.String(length=64), nullable=True),
            sa.Column('external_url', sa.String(length=1000), nullable=True),
            sa.Column('post_status', sa.String(length=32), nullable=False, server_default='publish'),
            sa.Column('target_site_url', sa.String(length=500), nullable=False),
            sa.Column('target_username', sa.String(length=255), nullable=False),
            sa.Column('error_code', sa.String(length=64), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['connection_id'], ['wordpress_connections.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['schedule_id'], ['blog_schedules.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['last_job_id'], ['blog_publication_jobs.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['blog_id'], ['blogs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['revision_id'], ['blog_revisions.id'], ondelete='RESTRICT'),
            sa.UniqueConstraint('company_id', 'publication_idempotency_key', name='uq_wp_pub_records_company_key'),
        )
        op.create_index('ix_wordpress_publication_records_id', 'wordpress_publication_records', ['id'], unique=False)
        op.create_index('ix_wp_pub_records_company_key', 'wordpress_publication_records', ['company_id', 'publication_idempotency_key'], unique=False)
        op.create_index('ix_wp_pub_records_blog_id', 'wordpress_publication_records', ['blog_id'], unique=False)
        op.create_index('ix_wp_pub_records_connection_id', 'wordpress_publication_records', ['connection_id'], unique=False)
        op.create_index('ix_wp_pub_records_schedule_id', 'wordpress_publication_records', ['schedule_id'], unique=False)
        op.create_index('ix_wp_pub_records_claim_lease_until', 'wordpress_publication_records', ['claim_lease_until'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'wordpress_publication_records' in tables:
        op.drop_index('ix_wp_pub_records_claim_lease_until', table_name='wordpress_publication_records')
        op.drop_index('ix_wp_pub_records_schedule_id', table_name='wordpress_publication_records')
        op.drop_index('ix_wp_pub_records_connection_id', table_name='wordpress_publication_records')
        op.drop_index('ix_wp_pub_records_blog_id', table_name='wordpress_publication_records')
        op.drop_index('ix_wp_pub_records_company_key', table_name='wordpress_publication_records')
        op.drop_index('ix_wordpress_publication_records_id', table_name='wordpress_publication_records')
        op.drop_table('wordpress_publication_records')

    if 'wordpress_connections' in tables:
        op.drop_index('ix_wordpress_connections_company_id', table_name='wordpress_connections')
        op.drop_index('ix_wordpress_connections_id', table_name='wordpress_connections')
        op.drop_table('wordpress_connections')
