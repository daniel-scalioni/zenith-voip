import httpx
from typing import Any


class WebhookDispatcher:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def dispatch(self, url: str, payload: dict[str, Any], secret: str | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if secret:
            headers["X-Webhook-Signature"] = secret

        try:
            resp = await self.client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return {"success": True, "status_code": resp.status_code, "response": resp.text}
        except httpx.RequestError as e:
            return {"success": False, "error": str(e)}

    async def dispatch_post_call(self, webhook_url: str, call_id: str, sentiment: dict, audit: dict, entities: dict):
        payload = {
            "event": "post_call",
            "call_id": call_id,
            "sentiment": sentiment,
            "audit": audit,
            "entities": entities,
            "timestamp": None,
        }
        return await self.dispatch(webhook_url, payload)

    async def close(self):
        await self.client.aclose()


webhook_dispatcher = WebhookDispatcher()
