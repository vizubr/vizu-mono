"""
Placeholder migration to match the current DB alembic_version.
This file was added because the database already contains the revision id
`e60514203590` but the corresponding migration file was missing from the repo.
Generating this placeholder lets Alembic operate and new revisions be created
in a deterministic way. Review and replace with a full schema migration if
you prefer an explicit DDL history.

Revision ID: e60514203590
Revises:
Create Date: 2025-11-26
"""

# revision identifiers, used by Alembic.
revision = "e60514203590"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # This is intentionally a no-op placeholder. The database already contains
    # the schema corresponding to this revision. If you prefer, replace this
    # with explicit op.create_table(...) statements to record schema history.
    pass


def downgrade():
    # No-op placeholder downgrade.
    pass
