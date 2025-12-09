"""merge experiment and multi-account branches
Revision ID: 18e89afd20d6
Revises: 20251202_add_multi_account_google, 20251215_add_experiment_tables
Create Date: 2025-12-03 16:11:01.676017

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '18e89afd20d6'
down_revision = ('20251202_add_multi_account_google', '20251215_add_experiment_tables')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
