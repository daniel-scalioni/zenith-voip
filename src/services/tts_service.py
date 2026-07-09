import asyncio
import io
import wave
from functools import lru_cache
from piper import PiperVoice
from src.config import settings


@lru_cache(maxsize=1)
def _load_voice(model_path: str) -> PiperVoice:
    return PiperVoice.load(model_path)


class PiperTTS:
    def __init__(self, model_path: str = settings.PIPER_VOICE_PATH):
        self.model_path = model_path

    async def synthesize(self, text: str, voice: str = "pt_BR", speaker_id: int = 0) -> bytes:
        return await asyncio.to_thread(self._synthesize_sync, text)

    def _synthesize_sync(self, text: str) -> bytes:
        pv = _load_voice(self.model_path)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            pv.synthesize_wav(text, wav_file)
        return buffer.getvalue()

    async def health(self) -> bool:
        try:
            await asyncio.to_thread(_load_voice, self.model_path)
            return True
        except Exception:
            return False
