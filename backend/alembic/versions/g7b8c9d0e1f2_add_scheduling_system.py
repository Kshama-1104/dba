"""Alembic migration: add scheduling system (Phase 10)

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Create blog_schedules table
    if 'blog_schedules' not in tables:
        op.create_table(
            'blog_schedules',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('blog_id', sa.Integer(), nullable=False),
            sa.Column('target_revision_id', sa.Integer(), nullable=False),
            sa.Column('scheduled_at_utc', sa.DateTime(timezone=True), nullable=False),
            sa.Column('local_scheduled_time', sa.DateTime(timezone=False), nullable=False),
            sa.Column('timezone', sa.String(length=64), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='SCHEDULED'),
            sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('reschedule_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('failure_code', sa.String(length=64), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=False),
            sa.Column('cancelled_by_user_id', sa.Integer(), nullable=True),
            sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['blog_id'], ['blogs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['target_revision_id'], ['blog_revisions.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['cancelled_by_user_id'], ['users.id']),
        )
        op.create_index('ix_blog_schedules_id', 'blog_schedules', ['id'], unique=False)
        op.create_index('ix_blog_schedules_company_id', 'blog_schedules', ['company_id'], unique=False)
        op.create_index('ix_blog_schedules_blog_id', 'blog_schedules', ['blog_id'], unique=False)
        op.create_index('ix_blog_schedules_target_revision_id', 'blog_schedules', ['target_revision_id'], unique=False)
        op.create_index('ix_blog_schedules_status', 'blog_schedules', ['status'], unique=False)
        op.create_index('ix_blog_schedules_scheduled_at_utc', 'blog_schedules', ['scheduled_at_utc'], unique=False)

        # Invariant 1: Exactly one active schedule per blog
        op.create_index(
            'uq_blog_active_schedule',
            'blog_schedules',
            ['blog_id'],
            unique=True,
            postgresql_where=sa.text("status IN ('SCHEDULED', 'QUEUED', 'RUNNING')")
        )
        # Due schedule polling index
        op.create_index(
            'ix_blog_schedules_due_poll',
            'blog_schedules',
            ['scheduled_at_utc'],
            unique=False,
            postgresql_where=sa.text("status = 'SCHEDULED'")
        )

    # 2. Create blog_schedule_events table
    if 'blog_schedule_events' not in tables:
        op.create_table(
            'blog_schedule_events',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('schedule_id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(length=64), nullable=False),
            sa.Column('actor_user_id', sa.Integer(), nullable=True),
            sa.Column('previous_scheduled_at_utc', sa.DateTime(timezone=True), nullable=True),
            sa.Column('new_scheduled_at_utc', sa.DateTime(timezone=True), nullable=True),
            sa.Column('previous_local_scheduled_time', sa.DateTime(timezone=False), nullable=True),
            sa.Column('new_local_scheduled_time', sa.DateTime(timezone=False), nullable=True),
            sa.Column('previous_timezone', sa.String(length=64), nullable=True),
            sa.Column('new_timezone', sa.String(length=64), nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['schedule_id'], ['blog_schedules.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
        )
        op.create_index('ix_blog_schedule_events_id', 'blog_schedule_events', ['id'], unique=False)
        op.create_index('ix_blog_schedule_events_schedule_id', 'blog_schedule_events', ['schedule_id'], unique=False)
        op.create_index('ix_blog_schedule_events_company_id', 'blog_schedule_events', ['company_id'], unique=False)
        op.create_index('ix_blog_schedule_events_event_type', 'blog_schedule_events', ['event_type'], unique=False)
        op.create_index('ix_blog_schedule_events_created_at', 'blog_schedule_events', ['created_at'], unique=False)

    # 3. Create blog_publication_jobs table
    if 'blog_publication_jobs' not in tables:
        op.create_table(
            'blog_publication_jobs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('schedule_id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('blog_id', sa.Integer(), nullable=False),
            sa.Column('revision_id', sa.Integer(), nullable=False),
            sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('idempotency_key', sa.String(length=128), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='QUEUED'),
            sa.Column('worker_id', sa.String(length=128), nullable=True),
            sa.Column('was_delayed', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('error_details', sa.Text(), nullable=True),
            sa.Column('external_reference', sa.String(length=256), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['schedule_id'], ['blog_schedules.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['blog_id'], ['blogs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['revision_id'], ['blog_revisions.id'], ondelete='RESTRICT'),
            sa.UniqueConstraint('idempotency_key', name='uq_pub_job_idempotency_key'),
        )
        op.create_index('ix_blog_publication_jobs_id', 'blog_publication_jobs', ['id'], unique=False)
        op.create_index('ix_blog_publication_jobs_schedule_id', 'blog_publication_jobs', ['schedule_id'], unique=False)
        op.create_index('ix_blog_publication_jobs_company_id', 'blog_publication_jobs', ['company_id'], unique=False)
        op.create_index('ix_blog_publication_jobs_blog_id', 'blog_publication_jobs', ['blog_id'], unique=False)
        op.create_index('ix_blog_publication_jobs_status', 'blog_publication_jobs', ['status'], unique=False)
        op.create_index('ix_blog_publication_jobs_lease_until', 'blog_publication_jobs', ['lease_until'], unique=False)

        # Invariant 2: Exactly one active publication job per schedule
        op.create_index(
            'uq_pub_job_one_active_per_schedule',
            'blog_publication_jobs',
            ['schedule_id'],
            unique=True,
            postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')")
        )
        # Lease recovery index
        op.create_index(
            'ix_blog_pub_jobs_lease_recovery',
            'blog_publication_jobs',
            ['lease_until'],
            unique=False,
            postgresql_where=sa.text("status = 'RUNNING'")
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'blog_publication_jobs' in tables:
        op.drop_index('ix_blog_pub_jobs_lease_recovery', table_name='blog_publication_jobs')
        op.drop_index('uq_pub_job_one_active_per_schedule', table_name='blog_publication_jobs')
        op.drop_table('blog_publication_jobs')

    if 'blog_schedule_events' in tables:
        op.drop_table('blog_schedule_events')

    if 'blog_schedules' in tables:
        op.drop_index('ix_blog_schedules_due_poll', table_name='blog_schedules')
        op.drop_index('uq_blog_active_schedule', table_name='blog_schedules')
        op.drop_table('blog_schedules')
