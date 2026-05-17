import httpx
from src.config import settings


class LocalLLMExtractor:
    def __init__(self, base_url: str = settings.OLLAMA_URL, model: str = "mistral:7b"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(timeout=30.0)

    async def sanitize(self, raw_value: str, entity_type: str, context: str = "") -> dict:
        prompt = (
            f"Extraia e corrija o seguinte dado do tipo '{entity_type}' do texto abaixo.\n"
            f"Contexto: {context}\n"
            f"Valor bruto: {raw_value}\n\n"
            f"Responda APENAS com JSON: {{\"entity_type\": \"{entity_type}\", \"value\": \"...\", "
            f"\"corrected\": true/false, \"confidence\": 0.0-1.0}}\n"
            f"Não inclua explicações."
        )
        try:
            resp = await self.client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "{}")
        except Exception as e:
            return {"entity_type": entity_type, "value": raw_value, "corrected": False, "confidence": 0.0, "error": str(e)}

    async def close(self):
        await self.client.aclose()
