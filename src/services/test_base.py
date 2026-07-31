from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.services.base import Factory, Repository, Strategy


class Base(DeclarativeBase):
    pass


class ServiceRecord(Base):
    __tablename__ = "service_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(100))


def _session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.delete = AsyncMock()
    return session


def _query_result(record=None, records=()):
    result = MagicMock()
    result.scalar_one_or_none.return_value = record
    result.scalars.return_value.all.return_value = list(records)
    return result


def _auto_fallback_strategy_class():
    try:
        from src.services.stt_autofallback import AutoFallbackSTT
    except ModuleNotFoundError as exc:
        pytest.fail(f"dependência pinada ausente: {exc}", pytrace=False)
    return AutoFallbackSTT


@pytest.mark.asyncio
async def test_repository_create_persists_real_sqlalchemy_model():
    # Arrange
    session = _session()
    repository = Repository(session, ServiceRecord)

    # Act
    record = await repository.create(tenant_id="tenant-a", name="first")

    # Assert
    assert isinstance(record, ServiceRecord)
    assert (record.tenant_id, record.name) == ("tenant-a", "first")
    session.add.assert_called_once_with(record)
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(record)


@pytest.mark.asyncio
async def test_repository_create_rolls_back_when_commit_fails():
    # Arrange
    session = _session()
    session.commit.side_effect = ConnectionError("database unavailable")
    repository = Repository(session, ServiceRecord)

    # Act
    with pytest.raises(ConnectionError, match="database unavailable"):
        await repository.create(tenant_id="tenant-a", name="not-persisted")

    # Assert
    session.rollback.assert_awaited_once_with()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_repository_get_and_find_by_return_database_results():
    # Arrange
    first = ServiceRecord(id=1, tenant_id="tenant-a", name="first")
    second = ServiceRecord(id=2, tenant_id="tenant-a", name="second")
    session = _session()
    session.execute.side_effect = [
        _query_result(record=first),
        _query_result(records=(first, second)),
    ]
    repository = Repository(session, ServiceRecord)

    # Act
    found = await repository.get(1)
    tenant_records = await repository.find_by(tenant_id="tenant-a")

    # Assert
    assert found is first
    assert tenant_records == [first, second]
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_repository_update_changes_and_persists_existing_record():
    # Arrange
    record = ServiceRecord(id=1, tenant_id="tenant-a", name="old")
    session = _session()
    session.execute.return_value = _query_result(record=record)
    repository = Repository(session, ServiceRecord)

    # Act
    updated = await repository.update(1, name="new")

    # Assert
    assert updated is record
    assert record.name == "new"
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(record)


@pytest.mark.asyncio
async def test_repository_update_rolls_back_when_commit_fails():
    # Arrange
    record = ServiceRecord(id=1, tenant_id="tenant-a", name="old")
    session = _session()
    session.execute.return_value = _query_result(record=record)
    session.commit.side_effect = ConnectionError("database unavailable")
    repository = Repository(session, ServiceRecord)

    # Act
    with pytest.raises(ConnectionError, match="database unavailable"):
        await repository.update(1, name="new")

    # Assert
    session.rollback.assert_awaited_once_with()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_repository_delete_removes_existing_record():
    # Arrange
    record = ServiceRecord(id=1, tenant_id="tenant-a", name="old")
    session = _session()
    session.execute.return_value = _query_result(record=record)
    repository = Repository(session, ServiceRecord)

    # Act
    deleted = await repository.delete(1)

    # Assert
    assert deleted is True
    session.delete.assert_awaited_once_with(record)
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_repository_delete_rolls_back_when_commit_fails():
    # Arrange
    record = ServiceRecord(id=1, tenant_id="tenant-a", name="old")
    session = _session()
    session.execute.return_value = _query_result(record=record)
    session.commit.side_effect = ConnectionError("database unavailable")
    repository = Repository(session, ServiceRecord)

    # Act
    with pytest.raises(ConnectionError, match="database unavailable"):
        await repository.delete(1)

    # Assert
    session.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_auto_fallback_strategy_uses_external_fallback_after_primary_error():
    # Arrange
    strategy_class = _auto_fallback_strategy_class()
    strategy = strategy_class.__new__(strategy_class)
    strategy.primary = MagicMock()
    strategy.primary.transcribe = AsyncMock(side_effect=TimeoutError("provider timeout"))
    strategy.fallback = MagicMock()
    strategy.fallback.transcribe = AsyncMock(
        return_value={"text": "fallback", "confidence": 0.8}
    )
    strategy.fallback_timeout_ms = 500

    # Act
    result = await strategy.transcribe(b"audio", mimetype="audio/wav")

    # Assert
    assert result == {
        "text": "fallback",
        "confidence": 0.8,
        "fallback_activated": True,
    }
    strategy.fallback.transcribe.assert_awaited_once_with(
        b"audio", mimetype="audio/wav"
    )


@pytest.mark.asyncio
async def test_auto_fallback_strategy_propagates_fallback_dependency_error():
    # Arrange
    strategy_class = _auto_fallback_strategy_class()
    strategy = strategy_class.__new__(strategy_class)
    strategy.primary = MagicMock()
    strategy.primary.transcribe = AsyncMock(return_value={"text": "", "confidence": 0.0})
    strategy.fallback = MagicMock()
    strategy.fallback.transcribe = AsyncMock(side_effect=ConnectionError("fallback offline"))
    strategy.fallback_timeout_ms = 500

    # Act
    with pytest.raises(ConnectionError, match="fallback offline"):
        await strategy.transcribe(b"audio")

    # Assert
    strategy.fallback.transcribe.assert_awaited_once_with(b"audio")


def test_strategy_and_factory_are_abstract_contracts():
    # Arrange / Act / Assert
    with pytest.raises(TypeError):
        Strategy()
    with pytest.raises(TypeError):
        Factory()
