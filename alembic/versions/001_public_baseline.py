"""Baseline pública do Zenith.

Revision ID: 001_public_baseline
Revises:
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001_public_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS public")
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("schema_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("schema_name", name="uq_tenants_schema_name"),
        schema="public",
    )
    op.create_table(
        "pbxs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("public.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("host", sa.String(128), nullable=False),
        sa.Column("port", sa.Integer(), server_default="5060", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="public",
    )
    op.create_index("idx_pbxs_tenant", "pbxs", ["tenant_id"], schema="public")


def downgrade() -> None:
    op.drop_index("idx_pbxs_tenant", table_name="pbxs", schema="public")
    op.drop_table("pbxs", schema="public")
    op.drop_table("tenants", schema="public")
