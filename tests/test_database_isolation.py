"""Segurança e lifecycle do banco descartável de pytest."""

import asyncio
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


def _contract():
    path = Path(__file__).with_name("conftest.py")
    assert path.exists(), "T085 deve implementar tests/conftest.py"
    spec = importlib.util.spec_from_file_location("zenith_test_conftest", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("url", [
    None, "", "postgresql+asyncpg://u:p@zenith-postgres/zenith",
    "postgresql+asyncpg://u:p@zenith-postgres-test/production",
    "postgresql+asyncpg://u:p@[::1]/zenith_test_a",
    "postgresql://u:p@zenith-postgres-test/zenith_test_a?host=zenith-postgres",
])
def test_guard_rejects_unsafe_dsn_variants(url):
    # Arrange
    contract = _contract()

    # Act / Assert
    with pytest.raises(ValueError):
        contract.validate_test_database_url(url)


def test_guard_accepts_case_insensitive_dedicated_dns_name():
    # Arrange
    contract = _contract()
    url = "postgresql+asyncpg://u:p@ZENITH-POSTGRES-TEST:5432/zenith_test_a1"

    # Act
    validated = contract.validate_test_database_url(url)

    # Assert
    assert validated == url


@pytest.mark.parametrize("url", [
    "postgresql://u:p@zenith-postgres-test:5432/zenith_test_a1",
    "postgresql+asyncpg://u:p@zenith%2dpostgres-test:5432/zenith_test_a1",
    "postgresql+asyncpg://u:p@zenith-postgres-test.:5432/zenith_test_a1",
    "postgresql+asyncpg://u:p@postgres-test:5432/zenith_test_a1",
    "postgresql+asyncpg://u:p@zenith-postgres-test.example:5432/zenith_test_a1",
    "postgresql+asyncpg://u:p@zenith-postgres-test@evil:5432/zenith_test_a1",
])
def test_guard_rejects_driver_alias_and_ambiguous_host_independently(url):
    # Arrange
    contract = _contract()

    # Act / Assert
    with pytest.raises(ValueError):
        contract.validate_test_database_url(url)


@pytest.mark.parametrize("url", [
    "postgresql+asyncpg://u:p@zenith-postgres-test:5432/zenith_test_a1?host=zenith-postgres",
    "postgresql+asyncpg://u:p@zenith-postgres-test:5433/zenith_test_a1",
])
def test_guard_rejects_query_host_override_and_nonstandard_port_independently(url):
    # Arrange
    contract = _contract()

    # Act / Assert
    with pytest.raises(ValueError):
        contract.validate_test_database_url(url)


def test_name_generation_remains_unique_under_concurrency():
    # Arrange
    contract = _contract()

    # Act
    with ThreadPoolExecutor(max_workers=16) as executor:
        names = set(executor.map(lambda _index: contract.unique_test_database_name(), range(500)))
        schemas = set(executor.map(lambda _index: contract.unique_test_schema_name(), range(500)))

    # Assert
    assert len(names) == len(schemas) == 500
    assert all(name.startswith("zenith_test_") and name.isidentifier() for name in names)
    assert all(name.startswith("tenant_test_") and name.isidentifier() for name in schemas)


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_mode", ["success", "exception", "cancellation"])
async def test_lifecycle_removes_exact_target_and_preserves_sentinel(
    test_database_server, exit_mode
):
    # Arrange
    contract = _contract()
    sentinel = await test_database_server.create_database(
        contract.unique_test_database_name()
    )
    target = None

    # Act / Assert
    try:
        try:
            async with contract.isolated_test_database(test_database_server.base_url) as resource:
                target = resource.database_name
                assert await test_database_server.database_exists(target)
                if exit_mode == "exception":
                    raise RuntimeError("intentional body failure")
                if exit_mode == "cancellation":
                    raise asyncio.CancelledError
        except (RuntimeError, asyncio.CancelledError):
            pass

        assert target is not None
        assert not await test_database_server.database_exists(target)
        assert await test_database_server.database_exists(sentinel)
    finally:
        await test_database_server.delete_database(sentinel)

    assert not await test_database_server.database_exists(sentinel)


@pytest.mark.asyncio
async def test_teardown_terminates_active_connection_before_drop(test_database_server):
    # Arrange
    contract = _contract()
    resource = None
    connection = None

    # Act
    async with contract.isolated_test_database(test_database_server.base_url) as resource:
        connection = await resource.open_connection()
        assert await test_database_server.database_exists(resource.database_name)

    # Assert
    assert not await test_database_server.database_exists(resource.database_name)
    assert connection.is_closed()
