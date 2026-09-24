"""Alembic migration: add reviewer workflow and update blog_reviews

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Extend blogstatus enum if running PostgreSQL
    if dialect_name == "postgresql":
        for val in ("pending_review", "approved", "changes_requested", "rejected"):
            op.execute(sa.text(f"ALTER TYPE blogstatus ADD VALUE IF NOT EXISTS '{val}'"))

    # 2. blog_reviews table handling
    if 'blog_reviews' not in tables:
        op.create_table(
            'blog_reviews',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('blog_id', sa.Integer(), nullable=False),
            sa.Column('submitted_revision_id', sa.Integer(), nullable=False),
            sa.Column('reviewer_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('submission_note', sa.Text(), nullable=True),
            sa.Column('feedback', sa.Text(), nullable=True),
            sa.Column('reviewer_comment', sa.Text(), nullable=True),
            sa.Column('submitted_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('decided_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['blog_id'], ['blogs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['submitted_revision_id'], ['blog_revisions.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_blog_reviews_company_id', 'blog_reviews', ['company_id'], unique=False)
        op.create_index('ix_blog_reviews_blog_id', 'blog_reviews', ['blog_id'], unique=False)
        op.create_index('ix_blog_reviews_submitted_revision_id', 'blog_reviews', ['submitted_revision_id'], unique=False)
        op.create_index('ix_blog_reviews_reviewer_id', 'blog_reviews', ['reviewer_id'], unique=False)
        op.create_index('ix_blog_reviews_status', 'blog_reviews', ['status'], unique=False)
        op.create_index('ix_blog_reviews_company_status', 'blog_reviews', ['company_id', 'status'], unique=False)
        op.create_index('ix_blog_reviews_blog_submitted_at', 'blog_reviews', ['blog_id', 'submitted_at'], unique=False)
    else:
        existing_cols = {c['name'] for c in inspector.get_columns('blog_reviews')}
        existing_fks = {fk['name']: fk for fk in inspector.get_foreign_keys('blog_reviews')}
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('blog_reviews')}

        # A. Make reviewer_id nullable with ON DELETE SET NULL
        if 'blog_reviews_reviewer_id_fkey' in existing_fks:
            op.drop_constraint('blog_reviews_reviewer_id_fkey', 'blog_reviews', type_='foreignkey')
        
        op.alter_column('blog_reviews', 'reviewer_id', existing_type=sa.Integer(), nullable=True)
        op.create_foreign_key(
            'blog_reviews_reviewer_id_fkey',
            'blog_reviews',
            'users',
            ['reviewer_id'],
            ['id'],
            ondelete='SET NULL',
        )

        # B. Alter status to VARCHAR(20)
        if dialect_name == "postgresql":
            op.execute(sa.text("ALTER TABLE blog_reviews ALTER COLUMN status TYPE VARCHAR(20) USING status::text;"))
            op.execute(sa.text("ALTER TABLE blog_reviews ALTER COLUMN status SET DEFAULT 'pending';"))
        else:
            op.alter_column('blog_reviews', 'status', existing_type=sa.String(length=20), nullable=False, server_default='pending')

        # C. Add submission_note column if not present
        if 'submission_note' not in existing_cols:
            op.add_column('blog_reviews', sa.Column('submission_note', sa.Text(), nullable=True))

        # D. Add submitted_revision_id column
        if 'submitted_revision_id' not in existing_cols:
            op.add_column('blog_reviews', sa.Column('submitted_revision_id', sa.Integer(), nullable=True))

            # Legacy backfill verification
            count_result = bind.execute(sa.text("SELECT count(*) FROM blog_reviews;")).scalar()
            if count_result > 0:
                # If there are rows, verify they can be deterministically and provably linked
                unmapped = bind.execute(sa.text("SELECT count(*) FROM blog_reviews WHERE submitted_revision_id IS NULL;")).scalar()
                if unmapped > 0:
                    raise RuntimeError(
                        f"Found {unmapped} legacy blog_reviews rows without verifiable submitted_revision_id. "
                        "Aborting migration to prevent data integrity compromise."
                    )

            op.alter_column('blog_reviews', 'submitted_revision_id', existing_type=sa.Integer(), nullable=False)
            op.create_foreign_key(
                'blog_reviews_submitted_revision_id_fkey',
                'blog_reviews',
                'blog_revisions',
                ['submitted_revision_id'],
                ['id'],
                ondelete='RESTRICT',
            )

        if 'ix_blog_reviews_submitted_revision_id' not in existing_indexes:
            op.create_index('ix_blog_reviews_submitted_revision_id', 'blog_reviews', ['submitted_revision_id'], unique=False)
        if 'ix_blog_reviews_company_status' not in existing_indexes:
            op.create_index('ix_blog_reviews_company_status', 'blog_reviews', ['company_id', 'status'], unique=False)
        if 'ix_blog_reviews_blog_submitted_at' not in existing_indexes:
            op.create_index('ix_blog_reviews_blog_submitted_at', 'blog_reviews', ['blog_id', 'submitted_at'], unique=False)


def downgrade() -> None:
    # Downgrade logic drops Phase 9 constraints and columns
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'blog_reviews' in tables:
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('blog_reviews')}
        if 'ix_blog_reviews_blog_submitted_at' in existing_indexes:
            op.drop_index('ix_blog_reviews_blog_submitted_at', table_name='blog_reviews')
        if 'ix_blog_reviews_company_status' in existing_indexes:
            op.drop_index('ix_blog_reviews_company_status', table_name='blog_reviews')
        if 'ix_blog_reviews_submitted_revision_id' in existing_indexes:
            op.drop_index('ix_blog_reviews_submitted_revision_id', table_name='blog_reviews')

        existing_fks = {fk['name']: fk for fk in inspector.get_foreign_keys('blog_reviews')}
        if 'blog_reviews_submitted_revision_id_fkey' in existing_fks:
            op.drop_constraint('blog_reviews_submitted_revision_id_fkey', 'blog_reviews', type_='foreignkey')

        existing_cols = {c['name'] for c in inspector.get_columns('blog_reviews')}
        if 'submitted_revision_id' in existing_cols:
            op.drop_column('blog_reviews', 'submitted_revision_id')
        if 'submission_note' in existing_cols:
            op.drop_column('blog_reviews', 'submission_note')
