"""Multitenancy somente em bancos descartáveis geridos por T068/T085."""

import asyncio
import importlib.util
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


EXPECTED_TENANT_TABLES = {"calls", "transcripts", "call_insights", "stt_metrics"}


def _isolation_contract():
    path = Path(__file__).with_name("conftest.py")
    assert path.exists(), "T085 deve implementar tests/conftest.py"
    spec = importlib.util.spec_from_file_location("zenith_test_conftest", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _assert_isolated_url(database_url: str) -> None:
    validated = _isolation_contract().validate_test_database_url(database_url)
    parsed = urlsplit(database_url)
    query = parse_qs(parsed.query)
    base_url = os.getenv("ZENITH_TEST_DATABASE_URL", "")
    base_database = urlsplit(base_url).path.removeprefix("/")
    assert validated == database_url
    assert parsed.scheme == "postgresql+asyncpg"
    assert parsed.hostname == "zenith-postgres-test"
    assert parsed.port == 5432
    assert parsed.path.removeprefix("/").startswith("zenith_test_")
    assert parsed.path.removeprefix("/") != base_database
    assert "host" not in query


@pytest.mark.asyncio
async def test_t074_tenant_schema_is_created_only_in_unique_database(
    isolated_test_database, monkeypatch
):
    # Arrange
    database_url = isolated_test_database.database_url
    _assert_isolated_url(database_url)
    test_engine = create_async_engine(database_url)
    from src.database import database

    monkeypatch.setattr(database, "engine", test_engine)
    schema_name = _isolation_contract().unique_test_schema_name()

    try:
        # Act
        await database.create_tenant_schema(schema_name)
        async with test_engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema_name"
                ),
                {"schema_name": schema_name},
            )

        # Assert
        assert set(rows.scalars()) == EXPECTED_TENANT_TABLES
    finally:
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_t074_tenant_schemas_isolate_call_rows(
    isolated_test_database, monkeypatch
):
    # Arrange
    database_url = isolated_test_database.database_url
    _assert_isolated_url(database_url)
    test_engine = create_async_engine(database_url)
    from src.database import database

    monkeypatch.setattr(database, "engine", test_engine)
    contract = _isolation_contract()
    schema_a = contract.unique_test_schema_name()
    schema_b = contract.unique_test_schema_name()
    call_id = f"call-{uuid4().hex}"

    try:
        await database.create_tenant_schema(schema_a)
        await database.create_tenant_schema(schema_b)

        # Act
        async with test_engine.begin() as connection:
            await connection.execute(text(f'SET LOCAL search_path TO "{schema_a}", public'))
            await connection.execute(
                text(
                    "INSERT INTO calls (id, call_id, direction, status) "
                    "VALUES (:id, :call_id, :direction, :status)"
                ),
                {
                    "id": uuid4(),
                    "call_id": call_id,
                    "direction": "inbound",
                    "status": "in_progress",
                },
            )
            count_b = await connection.scalar(
                text(f'SELECT COUNT(*) FROM "{schema_b}".calls WHERE call_id=:call_id'),
                {"call_id": call_id},
            )

        # Assert
        assert count_b == 0
    finally:
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_t074_green_rejects_malicious_schema_before_sql(
    isolated_test_database, monkeypatch
):
    # Arrange
    database_url = isolated_test_database.database_url
    _assert_isolated_url(database_url)
    test_engine = create_async_engine(database_url)
    from src.database import database

    monkeypatch.setattr(database, "engine", test_engine)
    malicious_schema = 'tenant_bad"; DROP SCHEMA public CASCADE; --'

    try:
        # Act / Assert
        with pytest.raises(ValueError):
            await database.create_tenant_schema(malicious_schema)
        async with test_engine.connect() as connection:
            public_exists = await connection.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.schemata "
                    "WHERE schema_name = :schema_name)"
                ),
                {"schema_name": "public"},
            )
        assert public_exists is True
    finally:
        await test_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_mode", ["exception", "cancellation"])
async def test_t074_isolated_database_teardown_preserves_sentinel(
    test_database_server, exit_mode
):
    # Arrange
    contract = _isolation_contract()
    sentinel = await test_database_server.create_database(
        contract.unique_test_database_name()
    )
    target = None

    # Act
    try:
        async with contract.isolated_test_database(
            test_database_server.base_url
        ) as resource:
            target = resource.database_name
            _assert_isolated_url(resource.database_url)
            if exit_mode == "exception":
                raise RuntimeError("t074 intentional failure")
            raise asyncio.CancelledError
    except (RuntimeError, asyncio.CancelledError):
        pass

    # Assert
    assert target is not None
    assert not await test_database_server.database_exists(target)
    assert await test_database_server.database_exists(sentinel)
