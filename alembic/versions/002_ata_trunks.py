"""Registro público de condomínios e troncos ATA.

Revision ID: 002_ata_trunks
Revises: 001_public_baseline
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002_ata_trunks"
down_revision: str | None = "001_public_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "condominiums",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pbx_id", UUID(as_uuid=True), sa.ForeignKey("public.pbxs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "pbx_id", "name", name="uq_condominiums_tenant_pbx_name"),
        schema="public",
    )
    op.create_index(
        "uq_condominiums_tenant_pbx_external_id",
        "condominiums", ["tenant_id", "pbx_id", "external_id"],
        unique=True, schema="public", postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_table(
        "ata_trunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pbx_id", UUID(as_uuid=True), sa.ForeignKey("public.pbxs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("condominium_id", UUID(as_uuid=True), sa.ForeignKey("public.condominiums.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prefix", sa.String(32), nullable=True),
        sa.Column("auth_username", sa.String(128), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("sip_profile", sa.String(32), nullable=False),
        sa.Column("transport", sa.String(8), nullable=False, server_default="udp"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("registration_status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("last_registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_unregistered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("sip_profile", "auth_username", name="uq_ata_trunks_profile_username"),
        sa.CheckConstraint("prefix IS NULL OR prefix ~ '^[0-9]{1,32}$'", name="ck_ata_trunks_prefix_digits"),
        sa.CheckConstraint("sip_profile IN ('internal', 'internal-7060')", name="ck_ata_trunks_sip_profile"),
        sa.CheckConstraint("transport = 'udp'", name="ck_ata_trunks_transport"),
        sa.CheckConstraint("registration_status IN ('unknown', 'registered', 'unregistered')", name="ck_ata_trunks_registration_status"),
        schema="public",
    )
    op.create_index(
        "uq_ata_trunks_tenant_prefix",
        "ata_trunks",
        ["tenant_id", "prefix"],
        unique=True,
        schema="public",
        postgresql_where=sa.text("prefix IS NOT NULL"),
    )
    op.create_index("idx_ata_trunks_scope", "ata_trunks", ["tenant_id", "pbx_id", "condominium_id"], schema="public")


def downgrade() -> None:
    op.drop_index("idx_ata_trunks_scope", table_name="ata_trunks", schema="public")
    op.drop_table("ata_trunks", schema="public")
    op.drop_index("uq_condominiums_tenant_pbx_external_id", table_name="condominiums", schema="public")
    op.drop_table("condominiums", schema="public")
