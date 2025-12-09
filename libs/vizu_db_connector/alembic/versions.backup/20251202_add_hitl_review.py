"""add_hitl_review_table

Revision ID: 20251202_add_hitl_review
Revises: 20251201_add_mcp_tables
Create Date: 2025-12-02

Adiciona tabela hitl_review para Human-in-the-Loop.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20251202_add_hitl_review"
down_revision: Union[str, None] = "20251201_add_mcp_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cria tabela hitl_review
    op.create_table(
        "hitl_review",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Identificadores
        sa.Column("session_id", sa.String(), nullable=False, index=True),
        sa.Column(
            "cliente_vizu_id", postgresql.UUID(as_uuid=True), nullable=False, index=True
        ),
        sa.Column("cliente_final_id", sa.Integer(), nullable=True, index=True),
        # Conteúdo da interação
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("agent_response", sa.Text(), nullable=False),
        # Metadata do roteamento
        sa.Column("criteria_triggered", sa.String(50), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("criteria_details", postgresql.JSONB(), server_default="{}"),
        # Metadata adicional
        sa.Column("trace_id", sa.String(), nullable=True),
        sa.Column("tools_called", postgresql.JSONB(), server_default="[]"),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("conversation_context", postgresql.JSONB(), server_default="[]"),
        # Status e timestamps
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        # Review data (preenchido pelo revisor)
        sa.Column("reviewer_id", sa.String(), nullable=True),
        sa.Column("corrected_response", sa.Text(), nullable=True),
        sa.Column("feedback_type", sa.String(50), nullable=True),
        sa.Column("feedback_notes", sa.Text(), nullable=True),
        sa.Column("feedback_tags", postgresql.JSONB(), server_default="[]"),
        # Langfuse integration
        sa.Column("langfuse_dataset_item_id", sa.String(), nullable=True),
    )

    # Foreign keys
    op.create_foreign_key(
        "fk_hitl_review_cliente_vizu",
        "hitl_review",
        "cliente_vizu",
        ["cliente_vizu_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "fk_hitl_review_cliente_final",
        "hitl_review",
        "cliente_final",
        ["cliente_final_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Índices adicionais para queries frequentes
    op.create_index(
        "ix_hitl_review_pending_by_client",
        "hitl_review",
        ["cliente_vizu_id", "status"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_index("ix_hitl_review_created_at", "hitl_review", ["created_at"])

    # RLS policy (se estiver usando RLS)
    # Nota: HitlReview é acessado internamente, não precisa de RLS por enquanto


def downgrade() -> None:
    op.drop_index("ix_hitl_review_created_at", table_name="hitl_review")
    op.drop_index("ix_hitl_review_pending_by_client", table_name="hitl_review")
    op.drop_constraint(
        "fk_hitl_review_cliente_final", "hitl_review", type_="foreignkey"
    )
    op.drop_constraint("fk_hitl_review_cliente_vizu", "hitl_review", type_="foreignkey")
    op.drop_table("hitl_review")
