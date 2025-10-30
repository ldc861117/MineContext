"""
Rename metadata columns to meta_data

Revision ID: 20251030_000002
Revises: 20251020_000001
Create Date: 2025-10-30 00:00:02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251030_000002"
down_revision = "20251020_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename metadata to meta_data to avoid SQLAlchemy reserved attribute"""
    # SQLite doesn't support ALTER COLUMN RENAME, so we need to use batch operations
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column("metadata", new_column_name="meta_data")
    
    with op.batch_alter_table("chunks") as batch_op:
        batch_op.alter_column("metadata", new_column_name="meta_data")
    
    with op.batch_alter_table("entities") as batch_op:
        batch_op.alter_column("metadata", new_column_name="meta_data")


def downgrade() -> None:
    """Revert meta_data back to metadata"""
    with op.batch_alter_table("entities") as batch_op:
        batch_op.alter_column("meta_data", new_column_name="metadata")
    
    with op.batch_alter_table("chunks") as batch_op:
        batch_op.alter_column("meta_data", new_column_name="metadata")
    
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column("meta_data", new_column_name="metadata")
