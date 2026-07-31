import pytest
from unittest.mock import AsyncMock

from src.services import calls


@pytest.mark.asyncio
async def test_create_call_record_persists_optional_numbers(monkeypatch):
    # Arrange
    repository = AsyncMock()
    monkeypatch.setattr(calls, "Repository", lambda *_args: repository)

    async def tenant_db(_schema):
        yield AsyncMock()

    monkeypatch.setattr(calls, "get_tenant_db", tenant_db)

    # Act
    await calls.create_call_record("tenant", "call", "pbx", "1001", "5511", "2099")

    # Assert
    repository.create.assert_awaited_once()
    kwargs = repository.create.await_args.kwargs
    assert kwargs["caller_number"] == "5511"
    assert kwargs["callee_number"] == "2099"


@pytest.mark.asyncio
async def test_create_call_record_keeps_existing_callers_compatible(monkeypatch):
    # Arrange
    repository = AsyncMock()
    monkeypatch.setattr(calls, "Repository", lambda *_args: repository)

    async def tenant_db(_schema):
        yield AsyncMock()

    monkeypatch.setattr(calls, "get_tenant_db", tenant_db)

    # Act
    await calls.create_call_record("tenant", "call", "pbx", "1001")

    # Assert
    kwargs = repository.create.await_args.kwargs
    assert kwargs["caller_number"] is None
    assert kwargs["callee_number"] is None
