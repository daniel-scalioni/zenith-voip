"""
T067 — Testes Red para provisionamento/restauração de tenant.

Contratos testados (ADR-011 / MIG-RF-02, MIG-RF-05):
  - provisionamento aceita UUIDs explícitos necessários à restauração
  - UUIDs fornecidos são preservados (não regenerados)
  - fluxo normal sem UUID informado continua funcionando
  - isolamento do schema por tenant é mantido
  - contrato público desacoplado de detalhes internos

Estes testes são coletáveis antes da implementação Green. Funções de
contrato ausentes causam falha de teste (não erro de importação).
"""
import importlib
import uuid

import pytest


def _load_contract(name: str):
    """Importa contrato Green de forma tolerante a ImportError."""
    try:
        mod = importlib.import_module("src.database.provision_contract")
        return getattr(mod, name, None)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# T067 — aceitar UUIDs explícitos
# ---------------------------------------------------------------------------

class TestProvisionAcceptsExplicitUUIDs:
    """MIG-RF-05: restauração deve aceitar UUIDs explícitos de tenant e PBX."""

    @pytest.mark.asyncio
    async def test_provision_with_explicit_tenant_uuid(self):
        """Provisionamento aceita UUID explícito para o tenant."""
        # Arrange
        provision = _load_contract("provision_tenant")
        assert provision is not None, "Contrato provision_tenant não encontrado"

        explicit_uuid = uuid.uuid4()

        # Act
        result = await provision(
            name="Tenant UUID Test",
            schema_name=f"tenant_{explicit_uuid.hex[:8]}",
            pbx_name="PBX Test",
            pbx_host="pbx.test.local",
            pbx_port=5060,
            tenant_id=explicit_uuid,
        )

        # Assert
        assert result["tenant_id"] == explicit_uuid

    @pytest.mark.asyncio
    async def test_provision_with_explicit_pbx_uuid(self):
        """Provisionamento aceita UUID explícito para o PBX."""
        # Arrange
        provision = _load_contract("provision_tenant")
        assert provision is not None

        explicit_tenant_uuid = uuid.uuid4()
        explicit_pbx_uuid = uuid.uuid4()

        # Act
        result = await provision(
            name="PBX UUID Test",
            schema_name=f"tenant_{explicit_tenant_uuid.hex[:8]}",
            pbx_name="PBX Test",
            pbx_host="pbx.test.local",
            pbx_port=5060,
            tenant_id=explicit_tenant_uuid,
            pbx_id=explicit_pbx_uuid,
        )

        # Assert
        assert result["pbx_id"] == explicit_pbx_uuid

    @pytest.mark.asyncio
    async def test_provision_with_both_explicit_uuids(self):
        """Restauração completa com ambos UUIDs preservados."""
        # Arrange
        provision = _load_contract("provision_tenant")
        assert provision is not None

        tenant_uuid = uuid.uuid4()
        pbx_uuid = uuid.uuid4()

        # Act
        result = await provision(
            name="Restore Test",
            schema_name=f"tenant_{tenant_uuid.hex[:8]}",
            pbx_name="PBX Restore",
            pbx_host="pbx.restore.local",
            pbx_port=7060,
            tenant_id=tenant_uuid,
            pbx_id=pbx_uuid,
        )

        # Assert
        assert result["tenant_id"] == tenant_uuid
        assert result["pbx_id"] == pbx_uuid


# ---------------------------------------------------------------------------
# T067 — preservar UUIDs
# ---------------------------------------------------------------------------

class TestProvisionPreservesUUIDs:
    """MIG-RF-05: UUIDs fornecidos devem ser preservados, nunca regenerados."""

    @pytest.mark.asyncio
    async def test_explicit_uuid_preserved_after_provision(self):
        """UUID informado é exatamente o UUID gravado no banco."""
        # Arrange
        provision = _load_contract("provision_tenant")
        get_tenant_by_id = _load_contract("get_tenant_by_id")
        assert provision is not None
        assert get_tenant_by_id is not None

        target_uuid = uuid.uuid4()

        # Act
        await provision(
            name="Preserve Test",
            schema_name=f"tenant_{target_uuid.hex[:8]}",
            pbx_name="PBX Preserve",
            pbx_host="pbx.preserve.local",
            pbx_port=5060,
            tenant_id=target_uuid,
        )

        # Assert
        tenant = await get_tenant_by_id(target_uuid)
        assert tenant is not None, "Tenant com UUID explícito deve existir após provisionamento"
        assert tenant.id == target_uuid

    @pytest.mark.asyncio
    async def test_explicit_uuid_not_overwritten_by_second_provision(self):
        """Segunda chamada de provisionamento não sobrescreve UUID existente."""
        # Arrange
        provision = _load_contract("provision_tenant")
        get_tenant_by_id = _load_contract("get_tenant_by_id")
        assert provision is not None
        assert get_tenant_by_id is not None

        target_uuid = uuid.uuid4()

        # Act
        await provision(
            name="Idempotent Test",
            schema_name=f"tenant_{target_uuid.hex[:8]}",
            pbx_name="PBX Idempotent",
            pbx_host="pbx.idempotent.local",
            pbx_port=5060,
            tenant_id=target_uuid,
        )
        await provision(
            name="Idempotent Test",
            schema_name=f"tenant_{target_uuid.hex[:8]}",
            pbx_name="PBX Idempotent",
            pbx_host="pbx.idempotent.local",
            pbx_port=5060,
            tenant_id=target_uuid,
        )

        # Assert
        tenant = await get_tenant_by_id(target_uuid)
        assert tenant.id == target_uuid


# ---------------------------------------------------------------------------
# T067 — fluxo normal sem UUID informado
# ---------------------------------------------------------------------------

class TestProvisionNormalFlowWithoutUUIDs:
    """MIG-RF-05: fluxo padrão (sem UUIDs explícitos) continua funcionando."""

    @pytest.mark.asyncio
    async def test_provision_without_uuid_generates_new(self):
        """Sem UUID explícito, novo UUID é gerado automaticamente."""
        # Arrange
        provision = _load_contract("provision_tenant")
        assert provision is not None

        # Act
        result = await provision(
            name="Auto UUID Test",
            schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
            pbx_name="PBX Auto",
            pbx_host="pbx.auto.local",
            pbx_port=5060,
        )

        # Assert
        assert result["tenant_id"] is not None
        assert isinstance(result["tenant_id"], uuid.UUID)

    @pytest.mark.asyncio
    async def test_provision_without_uuid_returns_all_fields(self):
        """Fluxo normal retorna tenant_id, pbx_id e schema_name."""
        # Arrange
        provision = _load_contract("provision_tenant")
        assert provision is not None

        # Act
        result = await provision(
            name="Full Return Test",
            schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
            pbx_name="PBX Full",
            pbx_host="pbx.full.local",
            pbx_port=5060,
        )

        # Assert
        assert "tenant_id" in result
        assert "pbx_id" in result
        assert "schema_name" in result

    @pytest.mark.asyncio
    async def test_provision_without_uuid_generates_unique_ids(self):
        """Duas chamadas sem UUID geram IDs diferentes."""
        # Arrange
        provision = _load_contract("provision_tenant")
        assert provision is not None

        # Act
        result_a = await provision(
            name="Unique Test A",
            schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
            pbx_name="PBX A",
            pbx_host="pbx.a.local",
            pbx_port=5060,
        )
        result_b = await provision(
            name="Unique Test B",
            schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
            pbx_name="PBX B",
            pbx_host="pbx.b.local",
            pbx_port=5060,
        )

        # Assert
        assert result_a["tenant_id"] != result_b["tenant_id"]
        assert result_a["pbx_id"] != result_b["pbx_id"]


# ---------------------------------------------------------------------------
# T067 — isolamento do schema por tenant
# ---------------------------------------------------------------------------

class TestProvisionSchemaIsolation:
    """MIG-RF-02: cada tenant recebe schema isolado com suas tabelas."""

    @pytest.mark.asyncio
    async def test_two_tenants_different_schemas(self):
        """Dois tenants provisionados possuem schemas distintos."""
        # Arrange
        provision = _load_contract("provision_tenant")
        assert provision is not None

        # Act
        result_a = await provision(
            name="Isolation A",
            schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
            pbx_name="PBX A",
            pbx_host="pbx.iso-a.local",
            pbx_port=5060,
        )
        result_b = await provision(
            name="Isolation B",
            schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
            pbx_name="PBX B",
            pbx_host="pbx.iso-b.local",
            pbx_port=5060,
        )

        # Assert
        assert result_a["schema_name"] != result_b["schema_name"]

    @pytest.mark.asyncio
    async def test_tenant_schema_starts_with_tenant_prefix(self):
        """Schema name de todo tenant começa com 'tenant_'."""
        # Arrange
        provision = _load_contract("provision_tenant")
        assert provision is not None

        # Act
        result = await provision(
            name="Prefix Test",
            schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
            pbx_name="PBX Prefix",
            pbx_host="pbx.prefix.local",
            pbx_port=5060,
        )

        # Assert
        assert result["schema_name"].startswith("tenant_")

    @pytest.mark.asyncio
    async def test_tenant_tables_not_in_public(self):
        """Tabelas de negócio de um tenant não são criadas em public."""
        # Arrange
        provision = _load_contract("provision_tenant")
        get_public_tables = _load_contract("get_public_tables")
        assert provision is not None
        assert get_public_tables is not None

        # Act
        await provision(
            name="Public Check Test",
            schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
            pbx_name="PBX Public",
            pbx_host="pbx.public.local",
            pbx_port=5060,
        )
        public_tables = await get_public_tables()

        # Assert
        tenant_only = {"calls", "transcripts", "call_insights", "stt_metrics"}
        assert not (tenant_only & public_tables), (
            f"Tabelas de tenant encontradas em public: {tenant_only & public_tables}"
        )

    @pytest.mark.asyncio
    async def test_provision_idempotent_for_existing_tenant(self):
        """Provisionamento repetido para mesmo schema não duplica dados."""
        # Arrange
        provision = _load_contract("provision_tenant")
        get_tenant_by_schema = _load_contract("get_tenant_by_schema")
        assert provision is not None
        assert get_tenant_by_schema is not None

        schema = f"tenant_{uuid.uuid4().hex[:8]}"

        # Act
        result_1 = await provision(
            name="Idempotent Tenant",
            schema_name=schema,
            pbx_name="PBX Idempotent",
            pbx_host="pbx.idempotent.local",
            pbx_port=5060,
        )
        result_2 = await provision(
            name="Idempotent Tenant",
            schema_name=schema,
            pbx_name="PBX Idempotent",
            pbx_host="pbx.idempotent.local",
            pbx_port=5060,
        )

        # Assert
        tenant = await get_tenant_by_schema(schema)
        assert tenant is not None
        assert result_1["tenant_id"] == result_2["tenant_id"]


# ---------------------------------------------------------------------------
# T067 — desacoplamento do contrato
# ---------------------------------------------------------------------------

class TestProvisionPublicContract:
    """Contrato público desacoplado de detalhes internos de implementação."""

    @pytest.mark.asyncio
    async def test_provision_returns_dict_not_model(self):
        """Retorno do provisionamento é dict serializável, não objeto ORM."""
        # Arrange
        provision = _load_contract("provision_tenant")
        assert provision is not None

        # Act
        result = await provision(
            name="Contract Test",
            schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
            pbx_name="PBX Contract",
            pbx_host="pbx.contract.local",
            pbx_port=5060,
        )

        # Assert
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_provision_result_has_required_keys(self):
        """Retorno contém as chaves obrigatórias do contrato público."""
        # Arrange
        provision = _load_contract("provision_tenant")
        assert provision is not None

        # Act
        result = await provision(
            name="Keys Test",
            schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
            pbx_name="PBX Keys",
            pbx_host="pbx.keys.local",
            pbx_port=5060,
        )

        # Assert
        required_keys = {"tenant_id", "pbx_id", "schema_name"}
        assert required_keys.issubset(set(result.keys())), (
            f"Chaves faltantes: {required_keys - set(result.keys())}"
        )

    @pytest.mark.asyncio
    async def test_restore_requires_explicit_tenant_uuid(self):
        """Restauração sem UUID de tenant deve falhar explicitamente."""
        # Arrange
        restore = _load_contract("restore_tenant")
        assert restore is not None, "Contrato restore_tenant não encontrado"

        # Act / Assert
        with pytest.raises((ValueError, TypeError)):
            await restore(
                schema_name=f"tenant_{uuid.uuid4().hex[:8]}",
                pbx_name="PBX Restore",
                pbx_host="pbx.restore.local",
                pbx_port=7060,
            )
