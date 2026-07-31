"""Aceitação da baseline Alembic em banco descartável (ADR-011)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


TENANT_TABLES = {"calls", "transcripts", "call_insights", "stt_metrics"}
EXPECTED_PUBLIC_TABLES = {"alembic_version", "tenants", "pbxs"}


def _upgrade(database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).parents[2], env=env, capture_output=True, text=True,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stderr


async def _snapshot(database_url: str) -> tuple[set[str], str, set[tuple[str, str]]]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            tables = set((await connection.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'"
            ))).scalars())
            revision = (await connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            ))).scalar_one()
            constraints = set((await connection.execute(text(
                "SELECT table_name, constraint_type FROM information_schema.table_constraints "
                "WHERE table_schema='public' AND table_name IN ('tenants','pbxs')"
            ))).tuples())
            return tables, revision, constraints
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_upgrade_empty_database_reaches_head_with_public_topology(isolated_test_database):
    # Arrange
    database_url = isolated_test_database.database_url

    # Act
    _upgrade(database_url)
    tables, revision, constraints = await _snapshot(database_url)

    # Assert
    assert revision == isolated_test_database.alembic_head
    assert tables == EXPECTED_PUBLIC_TABLES
    assert tables.isdisjoint(TENANT_TABLES)
    assert ("tenants", "PRIMARY KEY") in constraints
    assert ("tenants", "UNIQUE") in constraints
    assert ("pbxs", "PRIMARY KEY") in constraints
    assert ("pbxs", "FOREIGN KEY") in constraints


@pytest.mark.asyncio
async def test_second_upgrade_is_noop_at_same_head(isolated_test_database):
    # Arrange
    database_url = isolated_test_database.database_url
    _upgrade(database_url)
    before = await _snapshot(database_url)

    # Act
    _upgrade(database_url)
    after = await _snapshot(database_url)

    # Assert
    assert before == after
    assert after[1] == isolated_test_database.alembic_head
