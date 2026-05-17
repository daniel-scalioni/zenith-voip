from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.database import async_session_factory
from src.database.models import Transcript
from src.config import settings
import json


class TranscriptPersister:
    def __init__(self):
        self.redis = Redis.from_url(settings.REDIS_URL)
        self.batch_key_prefix = "transcripts:batch:"

    async def buffer_transcript(self, call_id: str, transcript_data: dict):
        key = f"{self.batch_key_prefix}{call_id}"
        await self.redis.rpush(key, json.dumps(transcript_data))

    async def flush_batch(self, call_id: str):
        key = f"{self.batch_key_prefix}{call_id}"
        batch = await self.redis.lrange(key, 0, -1)
        if not batch:
            return 0

        async with async_session_factory() as session:
            async with session.begin():
                for item in batch:
                    data = json.loads(item)
                    transcript = Transcript(
                        call_id=call_id,
                        channel=data.get("channel", "unknown"),
                        speaker=data.get("speaker"),
                        text=data.get("text", ""),
                        confidence=data.get("confidence"),
                        start_time=data.get("start_time", 0.0),
                        end_time=data.get("end_time", 0.0),
                        is_final=data.get("is_final", True),
                        metadata=data.get("metadata"),
                    )
                    session.add(transcript)

        await self.redis.delete(key)
        return len(batch)

    async def close(self):
        await self.redis.aclose()
