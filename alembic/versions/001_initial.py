"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-17 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("call_id", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("agent_uuid", sa.String(128), nullable=True),
        sa.Column("customer_uuid", sa.String(128), nullable=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), default="in_progress"),
        sa.Column("tenant_id", sa.String(64), nullable=True, index=True),
        sa.Column("caller_number", sa.String(32), nullable=True),
        sa.Column("callee_number", sa.String(32), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "transcripts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("speaker", sa.String(64), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("is_final", sa.Boolean(), default=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "call_insights",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sentiment", sa.String(32), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("entities", JSONB(), nullable=True),
        sa.Column("consensus_log", JSONB(), nullable=True),
        sa.Column("pop_checklist", JSONB(), nullable=True),
        sa.Column("anomaly_detected", sa.Boolean(), default=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_insight", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "stt_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("call_id", sa.String(128), nullable=True, index=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("chunk_duration_ms", sa.Float(), nullable=True),
        sa.Column("success", sa.Boolean(), default=True),
        sa.Column("fallback_activated", sa.Boolean(), default=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("stt_metrics")
    op.drop_table("call_insights")
    op.drop_table("transcripts")
    op.drop_table("calls")
