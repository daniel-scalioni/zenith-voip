"""
T066 — Testes Red para migrations Alembic (baseline pública).

Contratos testados (ADR-011 / MIG-RF-01, MIG-RF-03):
  - upgrade até head em banco vazio cria somente estruturas públicas
  - segunda execução é idempotente / no-op
  - nenhuma tabela de chamada/tenant (calls, transcripts, call_insights,
    stt_metrics) existe no schema public

Estes testes são coletáveis antes da implementação Green. Funções de
contrato Ausentes podem causar falha de importação durante collection —
uso de importlib minimiza isso.
"""
import importlib
import uuid

import pytest


def _load_contract(name: str):
    """Importa contrato Green de forma tolerante a ImportError."""
    try:
        mod = importlib.import_module("src.database.migrations_contract")
        return getattr(mod, name, None)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# T066 — upgrade até head em banco vazio
# ---------------------------------------------------------------------------

class TestUpgradeHeadOnEmptyDatabase:
    """MIG-RF-01 / MIG-RF-03: upgrade head cria baseline pública e é idempotente."""

    @pytest.mark.asyncio
    async def test_upgrade_head_creates_public_tables(self):
        """Após upgrade, public deve conter tenants, pbxs e alembic_version."""
        # Arrange
        run_upgrade = _load_contract("run_alembic_upgrade_head")
        get_public_tables = _load_contract("get_public_tables")
        assert run_upgrade is not None, "Contrato run_alembic_upgrade_head não encontrado"
        assert get_public_tables is not None, "Contrato get_public_tables não encontrado"

        # Act
        await run_upgrade()

        # Assert
        tables = await get_public_tables()
        assert "tenants" in tables
        assert "pbxs" in tables
        assert "alembic_version" in tables

    @pytest.mark.asyncio
    async def test_upgrade_head_no_error_on_empty(self):
        """Primeira execução em banco vazio não deve levantar exceção."""
        # Arrange
        run_upgrade = _load_contract("run_alembic_upgrade_head")
        assert run_upgrade is not None

        # Act — não deve levantar
        await run_upgrade()

        # Assert (implícito: sem exceção)

    @pytest.mark.asyncio
    async def test_second_run_is_idempotent(self):
        """MIG-RF-03: segunda execução de upgrade head não altera estado."""
        # Arrange
        run_upgrade = _load_contract("run_alembic_upgrade_head")
        get_public_tables = _load_contract("get_public_tables")
        get_alembic_revision = _load_contract("get_alembic_revision")
        assert run_upgrade is not None
        assert get_public_tables is not None
        assert get_alembic_revision is not None

        # Act
        await run_upgrade()
        revision_before = await get_alembic_revision()
        tables_before = await get_public_tables()

        await run_upgrade()
        revision_after = await get_alembic_revision()
        tables_after = await get_public_tables()

        # Assert
        assert revision_before == revision_after
        assert tables_before == tables_after


# ---------------------------------------------------------------------------
# T066 — nenhuma tabela de chamada em public
# ---------------------------------------------------------------------------

class TestNoBusinessTablesInPublic:
    """ADR-011: calls, transcripts, call_insights, stt_metrics NÃO existem em public."""

    TENANT_ONLY_TABLES = {"calls", "transcripts", "call_insights", "stt_metrics"}

    @pytest.mark.asyncio
    async def test_no_tenant_tables_in_public(self):
        """MIG-RF-01: nenhuma tabela de negócio no schema public."""
        # Arrange
        run_upgrade = _load_contract("run_alembic_upgrade_head")
        get_public_tables = _load_contract("get_public_tables")
        assert run_upgrade is not None
        assert get_public_tables is not None

        # Act
        await run_upgrade()
        tables = await get_public_tables()

        # Assert
        found = self.TENANT_ONLY_TABLES & tables
        assert not found, (
            f"Tabelas de tenant indevidamente em public: {found}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("table_name", ["calls", "transcripts", "call_insights", "stt_metrics"])
    async def test_specific_table_absent_in_public(self, table_name: str):
        """Cada tabela de tenant individualmente não deve existir em public."""
        # Arrange
        get_public_tables = _load_contract("get_public_tables")
        assert get_public_tables is not None

        # Act
        tables = await get_public_tables()

        # Assert
        assert table_name not in tables, (
            f"Tabela '{table_name}' não deveria existir em public"
        )

    @pytest.mark.asyncio
    async def test_only_global_structures_in_public(self):
        """Public contém apenas alembic_version, tenants e pbxs."""
        # Arrange
        run_upgrade = _load_contract("run_alembic_upgrade_head")
        get_public_tables = _load_contract("get_public_tables")
        assert run_upgrade is not None
        assert get_public_tables is not None

        # Act
        await run_upgrade()
        tables = await get_public_tables()

        # Assert
        allowed = {"alembic_version", "tenants", "pbxs"}
        unexpected = tables - allowed
        assert not unexpected, (
            f" Estruturas inesperadas em public: {unexpected}"
        )
