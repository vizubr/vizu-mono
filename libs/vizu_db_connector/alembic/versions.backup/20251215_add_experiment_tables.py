"""add experiment tables

Revision ID: 20251215_add_experiment_tables
Revises: 20251202_add_hitl_review
Create Date: 2025-12-15

Adiciona tabelas para o sistema de experimentos:
- experiment_run: Armazena execuções de experimento
- experiment_case: Armazena casos de teste individuais
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20251215_add_experiment_tables"
down_revision: Union[str, None] = "20251202_add_hitl_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create experiment_run table
    op.create_table(
        "experiment_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("manifest_name", sa.String(), nullable=False, index=True),
        sa.Column("manifest_version", sa.String(), nullable=False),
        sa.Column("manifest_json", postgresql.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("total_cases", sa.Integer(), default=0),
        sa.Column("completed_cases", sa.Integer(), default=0),
        sa.Column("success_cases", sa.Integer(), default=0),
        sa.Column("failure_cases", sa.Integer(), default=0),
        sa.Column("error_cases", sa.Integer(), default=0),
        sa.Column("hitl_routed_cases", sa.Integer(), default=0),
        sa.Column("langfuse_session_id", sa.String(), nullable=True),
        sa.Column("langfuse_dataset_id", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # Create experiment_case table
    op.create_table(
        "experiment_case",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiment_run.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("case_id", sa.String(), nullable=False, index=True),
        sa.Column(
            "cliente_id", postgresql.UUID(as_uuid=True), nullable=False, index=True
        ),
        sa.Column("cliente_name", sa.String(), nullable=False),
        # Input
        sa.Column("input_message", sa.Text(), nullable=False),
        sa.Column("expected_tool", sa.String(), nullable=True),
        sa.Column("expected_contains", postgresql.JSON(), nullable=True),
        # Output
        sa.Column("actual_response", sa.Text(), nullable=True),
        sa.Column("actual_tool_called", sa.String(), nullable=True),
        sa.Column("tools_called", postgresql.JSON(), nullable=True),
        sa.Column("model_used", sa.String(), nullable=True),
        # Classification
        sa.Column("outcome", sa.String(), nullable=False, default="needs_review"),
        sa.Column("classification", sa.String(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        # Assertions
        sa.Column("tool_assertion_passed", sa.Boolean(), nullable=True),
        sa.Column("contains_assertion_passed", sa.Boolean(), nullable=True),
        # HITL link
        sa.Column(
            "hitl_review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hitl_review.id"),
            nullable=True,
        ),
        sa.Column("hitl_routed_reason", sa.String(), nullable=True),
        # Langfuse link
        sa.Column("langfuse_trace_id", sa.String(), nullable=True),
        # Timing
        sa.Column("request_duration_ms", sa.Integer(), nullable=True),
        # Metadata
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_response", postgresql.JSON(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # Create indexes for better query performance
    op.create_index("ix_experiment_run_status", "experiment_run", ["status"])
    op.create_index("ix_experiment_case_outcome", "experiment_case", ["outcome"])
    op.create_index(
        "ix_experiment_case_classification", "experiment_case", ["classification"]
    )


def downgrade() -> None:
    op.drop_index("ix_experiment_case_classification", table_name="experiment_case")
    op.drop_index("ix_experiment_case_outcome", table_name="experiment_case")
    op.drop_index("ix_experiment_run_status", table_name="experiment_run")
    op.drop_table("experiment_case")
    op.drop_table("experiment_run")
