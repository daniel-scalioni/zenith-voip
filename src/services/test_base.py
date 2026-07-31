import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.base import (
    Factory,
    LLMStrategy,
    Repository,
    STTStrategy,
    Strategy,
    TTSStrategy,
)


class DummyModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class DummyStrategy(Strategy):
    async def execute(self, **kwargs):
        return "ok"


class DummySTT(STTStrategy):
    async def transcribe(self, audio_chunk: bytes, **kwargs) -> dict:
        return {"text": "hello"}


class DummyTTS(TTSStrategy):
    async def synthesize(self, text: str, **kwargs) -> bytes:
        return b"audio"


class DummyLLM(LLMStrategy):
    async def analyze(self, prompt: str, **kwargs) -> str:
        return "response"


class DummyFactory(Factory):
    def create_pipeline(self, tenant_id: str) -> dict[str, Strategy]:
        return {"stt": DummySTT(), "tts": DummyTTS(), "llm": DummyLLM()}


# --- Repository ---


@pytest.mark.asyncio
async def test_repository_create_adds_and_commits():
    # Arrange
    session = AsyncMock()
    repo = Repository(session, DummyModel)

    # Act
    result = await repo.create(name="test")

    # Assert
    assert result.name == "test"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(result)


@pytest.mark.asyncio
async def test_repository_get_returns_instance():
    # Arrange
    instance = DummyModel(id=1)
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = instance
    session.execute.return_value = result_mock
    repo = Repository(session, DummyModel)

    # Act
    result = await repo.get(1)

    # Assert
    assert result is instance


@pytest.mark.asyncio
async def test_repository_get_returns_none_when_not_found():
    # Arrange
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock
    repo = Repository(session, DummyModel)

    # Act
    result = await repo.get(999)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_repository_find_by_filters():
    # Arrange
    session = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = [DummyModel(id=1), DummyModel(id=2)]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars
    session.execute.return_value = result_mock
    repo = Repository(session, DummyModel)

    # Act
    results = await repo.find_by(id=1)

    # Assert
    assert len(results) == 2


@pytest.mark.asyncio
async def test_repository_update_sets_attributes_and_commits():
    # Arrange
    instance = DummyModel(id=1, name="old")
    session = AsyncMock()
    get_result = MagicMock()
    get_result.scalar_one_or_none.return_value = instance
    session.execute.return_value = get_result
    repo = Repository(session, DummyModel)

    # Act
    result = await repo.update(1, name="new")

    # Assert
    assert result.name == "new"
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_repository_update_returns_none_when_not_found():
    # Arrange
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock
    repo = Repository(session, DummyModel)

    # Act
    result = await repo.update(999, name="x")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_repository_delete_removes_and_returns_true():
    # Arrange
    instance = DummyModel(id=1)
    session = AsyncMock()
    get_result = MagicMock()
    get_result.scalar_one_or_none.return_value = instance
    session.execute.return_value = get_result
    repo = Repository(session, DummyModel)

    # Act
    result = await repo.delete(1)

    # Assert
    assert result is True
    session.delete.assert_awaited_once_with(instance)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_repository_delete_returns_false_when_not_found():
    # Arrange
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock
    repo = Repository(session, DummyModel)

    # Act
    result = await repo.delete(999)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_repository_create_propagates_commit_failure():
    # Arrange
    session = AsyncMock()
    session.commit.side_effect = Exception("db down")
    repo = Repository(session, DummyModel)

    # Act / Assert
    with pytest.raises(Exception, match="db down"):
        await repo.create(name="fail")


@pytest.mark.asyncio
async def test_repository_find_by_ignores_nonexistent_column():
    # Arrange
    session = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars
    session.execute.return_value = result_mock
    repo = Repository(session, DummyModel)

    # Act
    results = await repo.find_by(nonexistent_field="value")

    # Assert
    assert results == []


# --- Strategy ---


def test_strategy_subclass_requires_execute():
    # Arrange / Act / Assert
    with pytest.raises(TypeError):
        Strategy()


def test_strategy_concrete_subclass_works():
    # Arrange
    strategy = DummyStrategy()

    # Act
    result = strategy.execute()

    # Assert
    assert result == "ok"


def test_stt_strategy_requires_transcribe():
    # Arrange / Act / Assert
    with pytest.raises(TypeError):
        STTStrategy()


def test_tts_strategy_requires_synthesize():
    # Arrange / Act / Assert
    with pytest.raises(TypeError):
        TTSStrategy()


def test_llm_strategy_requires_analyze():
    # Arrange / Act / Assert
    with pytest.raises(TypeError):
        LLMStrategy()


def test_stt_subclass_works():
    # Arrange
    stt = DummySTT()

    # Act
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(stt.transcribe(b"audio"))

    # Assert
    assert result == {"text": "hello"}


def test_tts_subclass_works():
    # Arrange
    tts = DummyTTS()

    # Act
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(tts.synthesize("hi"))

    # Assert
    assert result == b"audio"


def test_llm_subclass_works():
    # Arrange
    llm = DummyLLM()

    # Act
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(llm.analyze("prompt"))

    # Assert
    assert result == "response"


# --- Factory ---


def test_factory_creates_pipeline():
    # Arrange
    factory = DummyFactory()

    # Act
    pipeline = factory.create_pipeline("tenant-1")

    # Assert
    assert "stt" in pipeline
    assert "tts" in pipeline
    assert "llm" in pipeline
    assert isinstance(pipeline["stt"], STTStrategy)
    assert isinstance(pipeline["tts"], TTSStrategy)
    assert isinstance(pipeline["llm"], LLMStrategy)


def test_factory_subclass_requires_create_pipeline():
    # Arrange / Act / Assert
    with pytest.raises(TypeError):
        Factory()


def test_factory_returns_independent_instances():
    # Arrange
    factory = DummyFactory()

    # Act
    p1 = factory.create_pipeline("t1")
    p2 = factory.create_pipeline("t2")

    # Assert
    assert p1["stt"] is not p2["stt"]
