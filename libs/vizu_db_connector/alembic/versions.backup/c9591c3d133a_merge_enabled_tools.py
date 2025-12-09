"""merge_enabled_tools
Revision ID: c9591c3d133a
Revises: 18e89afd20d6, 20251205_add_enabled_tools
Create Date: 2025-12-05 15:06:49.194484

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c9591c3d133a'
down_revision = ('18e89afd20d6', '20251205_add_enabled_tools')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
