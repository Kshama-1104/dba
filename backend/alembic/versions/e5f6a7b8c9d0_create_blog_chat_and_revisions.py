"""Alembic migration: create blog_chat_threads, blog_chat_messages, and blog_revisions tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. blog_chat_threads table
    if 'blog_chat_threads' not in tables:
        op.create_table(
            'blog_chat_threads',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('blog_id', sa.Integer(), nullable=False),
            sa.Column('editor_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('closed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['blog_id'], ['blogs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['editor_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('blog_id', name='uq_blog_chat_thread_blog_id'),
        )
        op.create_index('ix_blog_chat_threads_company_id', 'blog_chat_threads', ['company_id'], unique=False)
        op.create_index('ix_blog_chat_threads_blog_id', 'blog_chat_threads', ['blog_id'], unique=True)
        op.create_index('ix_blog_chat_threads_editor_id', 'blog_chat_threads', ['editor_id'], unique=False)
        op.create_index('ix_blog_chat_threads_status', 'blog_chat_threads', ['status'], unique=False)
        op.create_index('ix_blog_chat_threads_company_blog', 'blog_chat_threads', ['company_id', 'blog_id'], unique=False)
    else:
        # Existing table compatibility: add missing constraint / index if not present
        existing_uqs = [u['name'] for u in inspector.get_unique_constraints('blog_chat_threads') if u.get('name')]
        if 'uq_blog_chat_thread_blog_id' not in existing_uqs:
            # Check if any unique constraint exists on blog_id
            blog_id_unique = any('blog_id' in u.get('column_names', []) for u in inspector.get_unique_constraints('blog_chat_threads'))
            if not blog_id_unique:
                op.create_unique_constraint('uq_blog_chat_thread_blog_id', 'blog_chat_threads', ['blog_id'])

        existing_indexes = [idx['name'] for idx in inspector.get_indexes('blog_chat_threads') if idx.get('name')]
        if 'ix_blog_chat_threads_company_blog' not in existing_indexes:
            op.create_index('ix_blog_chat_threads_company_blog', 'blog_chat_threads', ['company_id', 'blog_id'], unique=False)

    # 2. blog_chat_messages table
    if 'blog_chat_messages' not in tables:
        op.create_table(
            'blog_chat_messages',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('thread_id', sa.Integer(), nullable=False),
            sa.Column('sender_type', sa.String(length=20), nullable=False),
            sa.Column('sender_id', sa.Integer(), nullable=True),
            sa.Column('message_type', sa.String(length=30), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('client_message_id', sa.String(length=64), nullable=True),
            sa.Column('message_metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['thread_id'], ['blog_chat_threads.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_blog_chat_messages_thread_id', 'blog_chat_messages', ['thread_id'], unique=False)
        op.create_index('ix_blog_chat_messages_sender_type', 'blog_chat_messages', ['sender_type'], unique=False)
        op.create_index('ix_blog_chat_messages_sender_id', 'blog_chat_messages', ['sender_id'], unique=False)
        op.create_index('ix_blog_chat_messages_message_type', 'blog_chat_messages', ['message_type'], unique=False)
        op.create_index('ix_blog_chat_messages_client_message_id', 'blog_chat_messages', ['client_message_id'], unique=False)
        op.create_index('ix_blog_chat_messages_created_at', 'blog_chat_messages', ['created_at'], unique=False)
        op.create_index('ix_blog_chat_messages_thread_created', 'blog_chat_messages', ['thread_id', 'created_at'], unique=False)
    else:
        # Existing table compatibility: check columns and add client_message_id if missing
        col_names = [col['name'] for col in inspector.get_columns('blog_chat_messages')]
        if 'client_message_id' not in col_names:
            op.add_column('blog_chat_messages', sa.Column('client_message_id', sa.String(length=64), nullable=True))
            op.create_index('ix_blog_chat_messages_client_message_id', 'blog_chat_messages', ['client_message_id'], unique=False)

        existing_indexes = [idx['name'] for idx in inspector.get_indexes('blog_chat_messages') if idx.get('name')]
        if 'ix_blog_chat_messages_thread_created' not in existing_indexes:
            op.create_index('ix_blog_chat_messages_thread_created', 'blog_chat_messages', ['thread_id', 'created_at'], unique=False)

    # 3. blog_revisions table
    if 'blog_revisions' not in tables:
        op.create_table(
            'blog_revisions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('blog_id', sa.Integer(), nullable=False),
            sa.Column('thread_id', sa.Integer(), nullable=True),
            sa.Column('message_id', sa.Integer(), nullable=True),
            sa.Column('editor_id', sa.Integer(), nullable=True),
            sa.Column('revision_number', sa.Integer(), nullable=False),
            sa.Column('revision_summary', sa.Text(), nullable=False),
            sa.Column('content_json', sa.JSON(), nullable=False),
            sa.Column('content_markdown', sa.Text(), nullable=False),
            sa.Column('seo_title', sa.String(length=255), nullable=True),
            sa.Column('meta_description', sa.Text(), nullable=True),
            sa.Column('primary_keyword', sa.String(length=255), nullable=True),
            sa.Column('restored_from_revision_id', sa.Integer(), nullable=True),
            sa.Column('validation_report', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['blog_id'], ['blogs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['thread_id'], ['blog_chat_threads.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['message_id'], ['blog_chat_messages.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['editor_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['restored_from_revision_id'], ['blog_revisions.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('blog_id', 'revision_number', name='uq_blog_revisions_number'),
        )
        op.create_index('ix_blog_revisions_company_id', 'blog_revisions', ['company_id'], unique=False)
        op.create_index('ix_blog_revisions_blog_id', 'blog_revisions', ['blog_id'], unique=False)
        op.create_index('ix_blog_revisions_thread_id', 'blog_revisions', ['thread_id'], unique=False)
        op.create_index('ix_blog_revisions_message_id', 'blog_revisions', ['message_id'], unique=False)
        op.create_index('ix_blog_revisions_editor_id', 'blog_revisions', ['editor_id'], unique=False)
        op.create_index('ix_blog_revisions_restored_from_id', 'blog_revisions', ['restored_from_revision_id'], unique=False)
        op.create_index('ix_blog_revisions_created_at', 'blog_revisions', ['created_at'], unique=False)
        op.create_index('ix_blog_revisions_company_blog', 'blog_revisions', ['company_id', 'blog_id'], unique=False)
        op.create_index('ix_blog_revisions_blog_revnum', 'blog_revisions', ['blog_id', 'revision_number'], unique=False)


def downgrade() -> None:
    op.drop_table('blog_revisions')
    # For blog_chat_messages and blog_chat_threads, drop or drop column based on migration management
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'blog_chat_messages' in tables:
        op.drop_table('blog_chat_messages')
    if 'blog_chat_threads' in tables:
        op.drop_table('blog_chat_threads')
