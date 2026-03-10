"""post creation mode

Revision ID: 0023_post_creation_mode
Revises: 0022_search_pg_indexes
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_post_creation_mode"
down_revision = "0022_search_pg_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('posts')]
    if 'creation_mode' not in columns:
        op.add_column("posts", sa.Column("creation_mode", sa.String(length=16), nullable=True, server_default="ai"))

    # Execute updates without try-except, they should be safe if table exists
    # Postgres requires casting JSON to text for LIKE operator
    op.execute(
        "UPDATE posts SET creation_mode='manual' "
        "WHERE (source_key LIKE 'uploads/%' OR source_url LIKE '%/uploads/%' OR cover_url LIKE '%/uploads/%' OR CAST(images AS TEXT) LIKE '%/uploads/%')"
    )
    op.execute("UPDATE posts SET creation_mode='ai' WHERE creation_mode IS NULL OR creation_mode=''")

    # Create index if not exists
    op.execute("CREATE INDEX IF NOT EXISTS ix_posts_creation_mode ON posts(creation_mode)")


def downgrade() -> None:
    op.drop_index("ix_posts_creation_mode", table_name="posts")
    op.drop_column("posts", "creation_mode")
