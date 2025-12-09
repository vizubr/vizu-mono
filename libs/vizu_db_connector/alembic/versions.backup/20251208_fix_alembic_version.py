"""Fix alembic_version column size

Revision ID: 20251208_fix_alembic_version
Revises: 20251215_add_experiment_tables
Create Date: 2025-12-08

Alters the alembic_version.version_num column to VARCHAR(255) to accommodate longer revision IDs.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251208_fix_alembic_version"
down_revision = "20251215_add_experiment_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alter the column type to accept longer revision IDs
    op.alter_column(
        'alembic_version',
        'version_num',
        existing_type=sa.String(32),
        type_=sa.String(255),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Revert to the smaller size (this might fail if there are long revision IDs)
    op.alter_column(
        'alembic_version',
        'version_num',
        existing_type=sa.String(255),
        type_=sa.String(32),
        existing_nullable=False,
    )
