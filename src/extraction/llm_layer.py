import json

import httpx
from src.config import settings


class LocalLLMExtractor:
    ENTITY_TYPES = frozenset(("cpf", "rg", "phone", "plate", "cep", "credit_card"))

    def __init__(self, base_url: str = settings.OLLAMA_URL, model: str = "mistral:7b"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(timeout=30.0)

    async def sanitize(self, raw_value: str, entity_type: str, context: str = "") -> dict:
        if not isinstance(raw_value, str) or not raw_value:
            return self._fallback(raw_value, entity_type, "valor bruto inválido")
        if entity_type not in self.ENTITY_TYPES:
            return self._fallback(raw_value, entity_type, "tipo de entidade inválido")
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
            payload = resp.json()
            response = payload.get("response")
            if not isinstance(response, str):
                raise ValueError("resposta da LLM ausente")
            result = json.loads(response)
            if not isinstance(result, dict):
                raise ValueError("resposta da LLM não é um objeto JSON")
            return result
        except Exception as e:
            return self._fallback(raw_value, entity_type, str(e))

    @staticmethod
    def _fallback(raw_value, entity_type: str, error: str) -> dict:
        return {
            "entity_type": entity_type,
            "value": raw_value,
            "corrected": False,
            "confidence": 0.0,
            "error": error,
        }

    async def close(self):
        await self.client.aclose()
