import httpx
from src.config import settings


class PiperTTS:
    def __init__(self, base_url: str = settings.PIPER_TTS_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def synthesize(self, text: str, voice: str = "pt_BR", speaker_id: int = 0) -> bytes:
        resp = await self.client.post(
            f"{self.base_url}/synthesize",
            json={"text": text, "voice": voice, "speaker_id": speaker_id},
        )
        resp.raise_for_status()
        return resp.content

    async def health(self) -> bool:
        try:
            resp = await self.client.get(f"{self.base_url}/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()
