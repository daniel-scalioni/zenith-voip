from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

ModelType = TypeVar("ModelType")


class Strategy(ABC):
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        ...


class STTStrategy(Strategy):
    @abstractmethod
    async def transcribe(self, audio_chunk: bytes, **kwargs) -> dict:
        ...


class TTSStrategy(Strategy):
    @abstractmethod
    async def synthesize(self, text: str, **kwargs) -> bytes:
        ...


class LLMStrategy(Strategy):
    @abstractmethod
    async def analyze(self, prompt: str, **kwargs) -> str:
        ...


class Repository(Generic[ModelType]):
    def __init__(self, session: AsyncSession, model_class: type[ModelType]):
        self._session = session
        self._model = model_class

    async def create(self, **kwargs) -> ModelType:
        instance = self._model(**kwargs)
        self._session.add(instance)
        await self._session.commit()
        await self._session.refresh(instance)
        return instance

    async def get(self, id: Any) -> ModelType | None:
        result = await self._session.execute(select(self._model).where(self._model.id == id))
        return result.scalar_one_or_none()

    async def find_by(self, **filters) -> list[ModelType]:
        query = select(self._model)
        for field, value in filters.items():
            column = getattr(self._model, field, None)
            if column is not None:
                query = query.where(column == value)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def update(self, id: Any, **kwargs) -> ModelType | None:
        instance = await self.get(id)
        if not instance:
            return None
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self._session.commit()
        await self._session.refresh(instance)
        return instance

    async def delete(self, id: Any) -> bool:
        instance = await self.get(id)
        if not instance:
            return False
        await self._session.delete(instance)
        await self._session.commit()
        return True


class Factory(ABC):
    @abstractmethod
    def create_pipeline(self, tenant_id: str) -> dict[str, Strategy]:
        ...
