"""Fixtures globais para os testes que vivem em ``src/`` e ``tests/``."""

import os

import pytest
import pytest_asyncio

from tests.conftest import (
    TestDatabaseServer,
    _configured_base_url,
    isolated_test_database as isolated_database_context,
)


@pytest_asyncio.fixture
async def test_database_server():
    yield TestDatabaseServer(_configured_base_url())


@pytest_asyncio.fixture
async def isolated_test_database():
    async with isolated_database_context(_configured_base_url()) as resource:
        yield resource


def pytest_collection_modifyitems(items):
    """Separa provas de infraestrutura real da suíte hermética de qualidade."""
    if os.getenv("ZENITH_RUN_INFRA_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="requer stack de integração (ZENITH_RUN_INFRA_TESTS=1)")
    for item in items:
        if item.path.name in {"test_infra.py", "test_chaos_restart.py"}:
            item.add_marker(skip)
