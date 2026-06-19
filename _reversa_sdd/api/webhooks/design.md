# Webhooks, Design

**Interface:** `dispatch_post_call(call_id, payload)` → HTTP POST para URL configurada
**Segurança:** Signature header incluso 🟡 (fire-and-forget, sem confirmação)
**Origem:** `src/api/webhooks.py:15-36` 🟢
