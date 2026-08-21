from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock

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


# --- create_ringing_call_record (fix GAP-RE-02) ---


@pytest.mark.asyncio
async def test_create_ringing_call_record_persists_ringing_status(monkeypatch):
    # Arrange
    repository = AsyncMock()
    monkeypatch.setattr(calls, "Repository", lambda *_args: repository)

    async def tenant_db(_schema):
        yield AsyncMock()

    monkeypatch.setattr(calls, "get_tenant_db", tenant_db)

    # Act
    await calls.create_ringing_call_record("tenant", "call", "pbx", "1001", "5511", "2099")

    # Assert
    kwargs = repository.create.await_args.kwargs
    assert kwargs["status"] == calls.CallStatus.ringing
    assert kwargs["caller_number"] == "5511"
    assert kwargs["callee_number"] == "2099"


# --- mark_call_in_progress (fix GAP-RE-02) ---


@pytest.mark.asyncio
async def test_mark_call_in_progress_updates_existing_ringing_record(monkeypatch):
    # Arrange
    existing = MagicMock(id="call-uuid")
    repository = AsyncMock()
    repository.find_by = AsyncMock(return_value=[existing])
    monkeypatch.setattr(calls, "Repository", lambda *_args: repository)

    async def tenant_db(_schema):
        yield AsyncMock()

    monkeypatch.setattr(calls, "get_tenant_db", tenant_db)

    # Act
    result = await calls.mark_call_in_progress("tenant", "call")

    # Assert
    assert result is True
    kwargs = repository.update.await_args.kwargs
    assert repository.update.await_args.args == ("call-uuid",)
    assert kwargs["status"] == calls.CallStatus.in_progress


@pytest.mark.asyncio
async def test_mark_call_in_progress_resets_started_at_so_duration_excludes_ring_time(monkeypatch):
    # Arrange: started_at nasce no CREATE (ringing); sem reset aqui, duration_seconds do
    # HANGUP passaria a incluir o tempo de toque, mudando a semântica pré-fix (talk time)
    existing = MagicMock(id="call-uuid")
    repository = AsyncMock()
    repository.find_by = AsyncMock(return_value=[existing])
    monkeypatch.setattr(calls, "Repository", lambda *_args: repository)

    async def tenant_db(_schema):
        yield AsyncMock()

    monkeypatch.setattr(calls, "get_tenant_db", tenant_db)

    # Act
    await calls.mark_call_in_progress("tenant", "call")

    # Assert
    kwargs = repository.update.await_args.kwargs
    assert isinstance(kwargs["started_at"], datetime)


@pytest.mark.asyncio
async def test_mark_call_in_progress_returns_false_when_no_record_exists(monkeypatch):
    # Arrange
    repository = AsyncMock()
    repository.find_by = AsyncMock(return_value=[])
    monkeypatch.setattr(calls, "Repository", lambda *_args: repository)

    async def tenant_db(_schema):
        yield AsyncMock()

    monkeypatch.setattr(calls, "get_tenant_db", tenant_db)

    # Act
    result = await calls.mark_call_in_progress("tenant", "call")

    # Assert
    assert result is False
    repository.update.assert_not_awaited()


# --- finalize_call_record classifica Hangup-Cause (fix GAP-RE-02) ---


@pytest.mark.asyncio
async def test_finalize_call_record_sets_completed_for_normal_hangup_cause(monkeypatch):
    # Arrange
    existing = MagicMock(id="call-uuid", started_at=datetime.now(timezone.utc))
    repository = AsyncMock()
    repository.find_by = AsyncMock(return_value=[existing])
    monkeypatch.setattr(calls, "Repository", lambda *_args: repository)

    async def tenant_db(_schema):
        yield AsyncMock()

    monkeypatch.setattr(calls, "get_tenant_db", tenant_db)

    # Act
    await calls.finalize_call_record("tenant", "call", hangup_cause="NORMAL_CLEARING")

    # Assert
    kwargs = repository.update.await_args.kwargs
    assert kwargs["status"] == calls.CallStatus.completed


@pytest.mark.asyncio
async def test_finalize_call_record_sets_failed_for_abnormal_hangup_cause(monkeypatch):
    # Arrange
    existing = MagicMock(id="call-uuid", started_at=datetime.now(timezone.utc))
    repository = AsyncMock()
    repository.find_by = AsyncMock(return_value=[existing])
    monkeypatch.setattr(calls, "Repository", lambda *_args: repository)

    async def tenant_db(_schema):
        yield AsyncMock()

    monkeypatch.setattr(calls, "get_tenant_db", tenant_db)

    # Act
    await calls.finalize_call_record("tenant", "call", hangup_cause="USER_BUSY")

    # Assert
    kwargs = repository.update.await_args.kwargs
    assert kwargs["status"] == calls.CallStatus.failed


@pytest.mark.asyncio
async def test_finalize_call_record_sets_failed_when_hangup_cause_missing(monkeypatch):
    # Arrange: causa ausente é tratada como anômala, não como encerramento normal silencioso
    existing = MagicMock(id="call-uuid", started_at=datetime.now(timezone.utc))
    repository = AsyncMock()
    repository.find_by = AsyncMock(return_value=[existing])
    monkeypatch.setattr(calls, "Repository", lambda *_args: repository)

    async def tenant_db(_schema):
        yield AsyncMock()

    monkeypatch.setattr(calls, "get_tenant_db", tenant_db)

    # Act
    await calls.finalize_call_record("tenant", "call")

    # Assert
    kwargs = repository.update.await_args.kwargs
    assert kwargs["status"] == calls.CallStatus.failed


@pytest.mark.asyncio
async def test_finalize_call_record_returns_silently_when_no_call_found(monkeypatch):
    # Arrange: regressão — CHANNEL_HANGUP sem Call correspondente não deve levantar
    repository = AsyncMock()
    repository.find_by = AsyncMock(return_value=[])
    monkeypatch.setattr(calls, "Repository", lambda *_args: repository)

    async def tenant_db(_schema):
        yield AsyncMock()

    monkeypatch.setattr(calls, "get_tenant_db", tenant_db)

    # Act
    await calls.finalize_call_record("tenant", "call", hangup_cause="NORMAL_CLEARING")

    # Assert
    repository.update.assert_not_awaited()
