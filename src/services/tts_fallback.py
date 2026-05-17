import os
from src.services.tts_service import PiperTTS


FALLBACK_WAV_DIR = os.path.join(os.path.dirname(__file__), "../../audio")


class TTSWithFallback:
    def __init__(self):
        self.primary = PiperTTS()
        self.fallback_wavs: dict[str, bytes] = {}

    async def synthesize(self, text: str, **kwargs) -> bytes:
        try:
            return await self.primary.synthesize(text, **kwargs)
        except Exception:
            return self._get_fallback(kwargs.get("fallback_key", "default"))

    def _get_fallback(self, key: str) -> bytes:
        wav_path = os.path.join(FALLBACK_WAV_DIR, f"{key}.wav")
        if os.path.exists(wav_path):
            with open(wav_path, "rb") as f:
                return f.read()
        return b""

    async def health(self) -> bool:
        return await self.primary.health()
