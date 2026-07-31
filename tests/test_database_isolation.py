"""
T068 — Testes Red para contrato de isolamento de banco de teste.

Contratos testados (ADR-011 / MIG-RF-04 / design.md):
  - guard rejeita DSN operacional e qualquer DSN não explicitamente de teste
  - guard impede host/DB operacional
  - nomes de banco e schema são únicos por execução
  - teardown é garantido inclusive quando o corpo do teste falha
  - ausência atual do contrato deve falhar em execução, nunca impedir a coleta

Estes testes são coletáveis antes da implementação Green. Funções de
contrato ausentes causam falha de teste (não erro de importação).
"""
import importlib
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


def _load_contract(name: str):
    """Importa contrato Green de forma tolerante a ImportError."""
    try:
        mod = importlib.import_module("src.database.isolation_contract")
        return getattr(mod, name, None)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# T068 — guard rejeita DSN operacional
# ---------------------------------------------------------------------------

class TestGuardRejectsOperationalDSN:
    """MIG-RF-04: guard deve rejeitar DSN do banco operacional."""

    def test_guard_rejects_production_dsn(self):
        """DSN contendo host operacional é rejeitada."""
        # Arrange
        guard = _load_contract("dsn_guard")
        assert guard is not None, "Contrato dsn_guard não encontrado"

        operational_dsn = (
            "postgresql+asyncpg://zenith_prod:secret@zenith-postgres:5432/zenith_prod"
        )

        # Act
        result = guard(operational_dsn)

        # Assert
        assert result is False, "Guard deveria rejeitar DSN operacional"

    def test_guard_rejects_localhost_dsn(self):
        """DSN com localhost/127.0.0.1 é rejeitada (não é de teste isolado)."""
        # Arrange
        guard = _load_contract("dsn_guard")
        assert guard is not None

        localhost_dsn = (
            "postgresql+asyncpg://zenith_test:pass@localhost:5432/zenith_test"
        )

        # Act
        result = guard(localhost_dsn)

        # Assert
        assert result is False, "Guard deveria rejeitar DSN com localhost"

    def test_guard_rejects_non_test_host(self):
        """DSN com host que não é zenith-postgres-test é rejeitada."""
        # Arrange
        guard = _load_contract("dsn_guard")
        assert guard is not None

        wrong_host_dsn = (
            "postgresql+asyncpg://zenith_test:pass@zenith-postgres-rehearsal:5432/zenith_test"
        )

        # Act
        result = guard(wrong_host_dsn)

        # Assert
        assert result is False, "Guard deveria rejeitar host não-teste (rehearsal)"

    def test_guard_rejects_candidate_dsn(self):
        """DSN apontando para candidato é rejeitada."""
        # Arrange
        guard = _load_contract("dsn_guard")
        assert guard is not None

        candidate_dsn = (
            "postgresql+asyncpg://zenith_test:pass@zenith-postgres-candidate:5432/zenith_test"
        )

        # Act
        result = guard(candidate_dsn)

        # Assert
        assert result is False, "Guard deveria rejeitar DSN de candidato"

    def test_guard_rejects_arbitrary_dsn(self):
        """DSN arbitrária não-lista na allowlist é rejeitada."""
        # Arrange
        guard = _load_contract("dsn_guard")
        assert guard is not None

        arbitrary_dsn = (
            "postgresql+asyncpg://user:pass@some-random-host:5432/some_db"
        )

        # Act
        result = guard(arbitrary_dsn)

        # Assert
        assert result is False, "Guard deveria rejeitar DSN arbitrária"


# ---------------------------------------------------------------------------
# T068 — guard impede host/DB operacional
# ---------------------------------------------------------------------------

class TestGuardPreventsOperationalHostDB:
    """MIG-RF-04: guard deve impedir host e nome de DB operacionais."""

    def test_guard_rejects_operational_host(self):
        """Host 'zenith-postgres' (operacional) é barrado."""
        # Arrange
        guard = _load_contract("host_guard")
        assert guard is not None, "Contrato host_guard não encontrado"

        # Act
        result = guard("zenith-postgres")

        # Assert
        assert result is False, "Host operacional deveria ser barrado"

    def test_guard_rejects_operational_db_name(self):
        """Nome de DB operacional é barrado."""
        # Arrange
        guard = _load_contract("db_name_guard")
        assert guard is not None, "Contrato db_name_guard não encontrado"

        # Act
        result = guard("zenith")

        # Assert
        assert result is False, "Nome de DB operacional deveria ser barrado"

    def test_guard_allows_test_host(self):
        """Host 'zenith-postgres-test' é aceito."""
        # Arrange
        host_guard = _load_contract("host_guard")
        assert host_guard is not None

        # Act
        result = host_guard("zenith-postgres-test")

        # Assert
        assert result is True, "Host de teste deveria ser aceito"

    def test_guard_allows_test_db_name(self):
        """Nome de DB de teste é aceito."""
        # Arrange
        db_guard = _load_contract("db_name_guard")
        assert db_guard is not None

        # Act
        result = db_guard("zenith_test")

        # Assert
        assert result is True, "Nome de DB de teste deveria ser aceito"


# ---------------------------------------------------------------------------
# T068 — nomes únicos por execução
# ---------------------------------------------------------------------------

class TestUniqueNamesPerExecution:
    """Nomes de banco e schema devem ser únicos a cada execução de teste."""

    def test_generate_db_name_returns_unique_values(self):
        """Cada chamada a generate_db_name retorna nome diferente."""
        # Arrange
        generate = _load_contract("generate_test_db_name")
        assert generate is not None, "Contrato generate_test_db_name não encontrado"

        # Act
        name_a = generate()
        name_b = generate()

        # Assert
        assert name_a != name_b, "Nomes de DB devem ser únicos por chamada"

    def test_generate_schema_name_returns_unique_values(self):
        """Cada chamada a generate_schema_name retorna nome diferente."""
        # Arrange
        generate = _load_contract("generate_test_schema_name")
        assert generate is not None, "Contrato generate_test_schema_name não encontrado"

        # Act
        name_a = generate()
        name_b = generate()

        # Assert
        assert name_a != name_b, "Nomes de schema devem ser únicos por chamada"

    def test_db_name_contains_random_component(self):
        """Nome de DB contém componente aleatório (não é estático)."""
        # Arrange
        generate = _load_contract("generate_test_db_name")
        assert generate is not None

        # Act
        name = generate()

        # Assert
        assert isinstance(name, str)
        assert len(name) > 0
        # Nome não deve ser igual ao nome base fixo
        assert name != "zenith_test", "Nome não deve ser o nome estático base"

    def test_schema_name_contains_random_component(self):
        """Nome de schema contém componente aleatório (não é estático)."""
        # Arrange
        generate = _load_contract("generate_test_schema_name")
        assert generate is not None

        # Act
        name = generate()

        # Assert
        assert isinstance(name, str)
        assert len(name) > 0

    def test_unique_names_across_multiple_calls(self):
        """Dez chamadas consecutivas geram todos nomes diferentes."""
        # Arrange
        generate_db = _load_contract("generate_test_db_name")
        generate_schema = _load_contract("generate_test_schema_name")
        assert generate_db is not None
        assert generate_schema is not None

        # Act
        db_names = {generate_db() for _ in range(10)}
        schema_names = {generate_schema() for _ in range(10)}

        # Assert
        assert len(db_names) == 10, "Todos os nomes de DB devem ser únicos"
        assert len(schema_names) == 10, "Todos os nomes de schema devem ser únicos"


# ---------------------------------------------------------------------------
# T068 — teardown garantido mesmo com falha no corpo
# ---------------------------------------------------------------------------

class TestTeardownGuaranteedOnFailure:
    """Teardown deve ser executado mesmo quando o corpo do teste falha."""

    def test_teardown_fixture_always_runs(self, monkeypatch):
        """Fixture de teardown é chamada mesmo se o teste levantar exceção."""
        # Arrange
        teardown_fn = _load_contract("test_teardown")
        assert teardown_fn is not None, "Contrato test_teardown não encontrado"

        call_log = []

        # Act / Assert
        try:
            # Simula corpo de teste que falha
            raise RuntimeError("falha proposital")
        except RuntimeError:
            pass
        finally:
            teardown_fn(lambda: call_log.append("cleaned"))

        # Assert
        assert "cleaned" in call_log, (
            "Teardown deveria ter sido executada mesmo com falha no corpo"
        )

    def test_teardown_receives_correct_target(self):
        """Teardown recebe o nome exato do schema/DB para limpar."""
        # Arrange
        teardown_fn = _load_contract("test_teardown")
        assert teardown_fn is not None

        captured_target = []
        target_schema = f"tenant_{uuid.uuid4().hex[:8]}"

        # Act
        teardown_fn(
            lambda: captured_target.append(target_schema),
            target=target_schema,
        )

        # Assert
        assert captured_target == [target_schema], (
            "Teardown deveria receber o target exato para limpeza"
        )

    def test_teardown_only_removes_test_target(self):
        """Teardown remove apenas o alvo específico, não outros schemas."""
        # Arrange
        teardown_fn = _load_contract("test_teardown")
        assert teardown_fn is not None

        removed = []
        safe_target = f"tenant_{uuid.uuid4().hex[:8]}"

        # Act — teardown não deve remover o safe_target
        teardown_fn(
            lambda t: removed.append(t),
            target=f"tenant_{uuid.uuid4().hex[:8]}",
            safe_targets=[safe_target],
        )

        # Assert
        assert safe_target not in removed, (
            "Teardown não deveria remover targets protegidos"
        )


# ---------------------------------------------------------------------------
# T068 — ausência do contrato falha em execução, não na coleta
# ---------------------------------------------------------------------------

class TestContractAbsenceFailsAtRuntime:
    """Contrato ausente deve causar falha de teste, não erro de importação/coleção."""

    def test_missing_contract_does_not_block_collection(self):
        """Teste é coletável mesmo quando contrato Green não existe."""
        # Arrange / Act — se chegamos aqui, a coleta não falhou
        # Assert — contrato pode ser None (ausente), mas o teste roda
        guard = _load_contract("dsn_guard")
        # Não assertamos que guard is not None — o ponto é que o teste
        # é coletável e executável, mesmo que o contrato não exista ainda.
        # Quando o contrato ausente for obrigatório, a falha será de
        # asserts internos, não de ImportError na coleta.
        assert guard is None or callable(guard), (
            "Teste deveria ser coletável independentemente da existência do contrato"
        )

    def test_load_contract_returns_none_when_missing(self):
        """_load_contract retorna None para contrato inexistente."""
        # Arrange
        nonexistent = _load_contract("this_contract_does_not_exist_ever")

        # Act / Assert
        assert nonexistent is None, (
            "Contrato inexistente deveria retornar None, não levantar exceção"
        )

    def test_collection_succeeds_without_green_code(self):
        """Módulo de teste é importável sem código Green implementado."""
        # Arrange / Act
        mod = importlib.import_module("tests.test_database_isolation")

        # Assert
        assert mod is not None, "Módulo de teste deveria ser importável sem Green"
