"""merge_heads
Revision ID: 20251128_merge_heads
Revises: b7c0618d7931, 20251128_merge_cfg, 20251128_merge_configuracao_into_cliente_vizu
Create Date: 2025-11-28

Merge multiple parallel heads created during development into a single head
so Alembic can produce a linear migration history. This is a no-op merge
revision: it records that the branches have been reconciled.
"""

# revision identifiers, used by Alembic.
revision = "20251128_merge_heads"
down_revision = (
    "b7c0618d7931",
    "20251128_merge_cfg",
    "20251128_merge_configuracao_into_cliente_vizu",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This merge revision intentionally does not perform DDL. It simply
    # records that the parallel branches were reconciled.
    pass


def downgrade() -> None:
    # Downgrade would re-introduce branching; avoid implementing.
    pass
