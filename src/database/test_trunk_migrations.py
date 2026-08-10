import importlib.util
import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


MIGRATION_PATH = Path(__file__).parents[2] / "alembic/versions/002_ata_trunks.py"


def _migration_module():
    spec = importlib.util.spec_from_file_location("migration_002_ata_trunks", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_trunk_migration_descends_from_public_baseline():
    # Arrange
    module = _migration_module()

    # Act
    revision = module.revision
    down_revision = module.down_revision

    # Assert
    assert revision == "002_ata_trunks"
    assert down_revision == "001_public_baseline"


def test_trunk_migration_defines_additive_public_tables():
    # Arrange
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    upgrade_source = inspect.getsource(_migration_module().upgrade)

    # Act
    create_calls = source.count("op.create_table(")

    # Assert
    assert create_calls == 2
    assert '"condominiums"' in source
    assert '"ata_trunks"' in source
    assert 'schema="public"' in source
    assert 'schema="tenant_' not in source
    assert "op.drop_table(" not in upgrade_source


def test_trunk_migration_allows_missing_prefix_with_partial_uniqueness():
    # Arrange
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    # Act
    prefix_column = 'sa.Column("prefix", sa.String(32), nullable=True)'

    # Assert
    assert prefix_column in source
    assert 'postgresql_where=sa.text("prefix IS NOT NULL")' in source


def _upgrade(database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).parents[2], env=env, capture_output=True, text=True,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stderr


async def _snapshot(database_url: str):
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            public_tables = set((await connection.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            ))).scalars())
            tenant_schemas = set((await connection.execute(text(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'tenant_%'"
            ))).scalars())
            revision = (await connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            ))).scalar_one()
            return public_tables, tenant_schemas, revision
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_trunk_migration_is_repeatable_and_does_not_create_tenant_schema(isolated_test_database):
    # Arrange
    database_url = isolated_test_database.database_url

    # Act
    _upgrade(database_url)
    first = await _snapshot(database_url)
    _upgrade(database_url)
    second = await _snapshot(database_url)

    # Assert
    assert first == second
    assert {"condominiums", "ata_trunks"} <= first[0]
    assert first[1] == set()
    assert first[2] == "002_ata_trunks"
