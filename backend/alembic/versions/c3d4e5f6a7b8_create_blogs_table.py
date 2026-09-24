"""Alembic migration: create blogs table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Cleanly replace any pre-Alembic unmanaged prototype 'blogs' table and enum
    bind.execute(sa.text("DROP TABLE IF EXISTS blogs CASCADE;"))
    bind.execute(sa.text("DROP TYPE IF EXISTS blogstatus CASCADE;"))

    # 2. Create canonical blogstatus enum
    # Enum creation handled by create_table

    # 3. Create canonical blogs table per Phase 6 specifications
    op.create_table(
        'blogs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('topic_candidate_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=True),
        sa.Column('primary_keyword', sa.String(length=255), nullable=True),
        sa.Column('seo_title', sa.String(length=255), nullable=True),
        sa.Column('meta_description', sa.Text(), nullable=True),
        sa.Column('content_json', sa.JSON(), nullable=False),
        sa.Column('content_markdown', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('generating', 'draft', 'generation_failed', name='blogstatus'), nullable=False, server_default='draft'),
        sa.Column('format_version', sa.Integer(), nullable=True),
        sa.Column('generation_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_candidate_id'], ['topic_candidates.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('topic_candidate_id', name='uq_blogs_topic_candidate_id'),
    )

    # 4. Create indexes
    op.create_index(op.f('ix_blogs_company_id'), 'blogs', ['company_id'], unique=False)
    op.create_index(op.f('ix_blogs_topic_candidate_id'), 'blogs', ['topic_candidate_id'], unique=True)
    op.create_index(op.f('ix_blogs_status'), 'blogs', ['status'], unique=False)
    op.create_index(op.f('ix_blogs_created_by_user_id'), 'blogs', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_blogs_slug'), 'blogs', ['slug'], unique=False)

    # 5. Restore foreign keys from unmanaged tables if they exist
    bind.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'blog_chat_threads') THEN
                ALTER TABLE blog_chat_threads ADD CONSTRAINT blog_chat_threads_blog_id_fkey FOREIGN KEY (blog_id) REFERENCES blogs(id) ON DELETE CASCADE;
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'blog_reviews') THEN
                ALTER TABLE blog_reviews ADD CONSTRAINT blog_reviews_blog_id_fkey FOREIGN KEY (blog_id) REFERENCES blogs(id) ON DELETE CASCADE;
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'blog_format_overrides') THEN
                ALTER TABLE blog_format_overrides ADD CONSTRAINT fk_blog_format_overrides_blog_id_blogs FOREIGN KEY (blog_id) REFERENCES blogs(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """))


def downgrade() -> None:
    op.drop_index(op.f('ix_blogs_slug'), table_name='blogs')
    op.drop_index(op.f('ix_blogs_created_by_user_id'), table_name='blogs')
    op.drop_index(op.f('ix_blogs_status'), table_name='blogs')
    op.drop_index(op.f('ix_blogs_topic_candidate_id'), table_name='blogs')
    op.drop_index(op.f('ix_blogs_company_id'), table_name='blogs')
    op.drop_table('blogs')
    sa.Enum(name='blogstatus').drop(op.get_bind(), checkfirst=True)
