import asyncio
from src.services.base import STTStrategy
from src.services.stt_deepgram import DeepgramSTT
from src.services.stt_whisper import WhisperCppSTT
from src.config import settings


class AutoFallbackSTT(STTStrategy):
    def __init__(self):
        self.primary = DeepgramSTT()
        self.fallback = WhisperCppSTT()
        self.fallback_timeout_ms = settings.STT_FALLBACK_TIMEOUT_MS

    async def transcribe(self, audio_chunk: bytes, **kwargs) -> dict:
        try:
            result = await asyncio.wait_for(
                self.primary.transcribe(audio_chunk, **kwargs),
                timeout=self.fallback_timeout_ms / 1000,
            )
            if result.get("text") and result.get("confidence", 0) > 0.3:
                result["fallback_activated"] = False
                return result
        except (asyncio.TimeoutError, Exception):
            pass

        fallback_result = await self.fallback.transcribe(audio_chunk, **kwargs)
        fallback_result["fallback_activated"] = True
        return fallback_result
