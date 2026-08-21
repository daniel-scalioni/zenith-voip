# Webhooks, Design

**Interface:** `dispatch_post_call(call_id, payload)` → HTTP POST para URL configurada
**Segurança:** Signature header incluso 🟡 (fire-and-forget, sem confirmação)
**Origem:** `src/api/webhooks.py:15-36` 🔴 — código existe mas está **desconectado**: nenhum
outro módulo em `src/` chama `dispatch_post_call`/`webhook_dispatcher` (confirmado via grep,
2026-08-21). Não há endpoint, worker ou handler ESL que o invoque. Ver GAP-04 (`gaps.md`) para
o mapeamento completo da cadeia pós-chamada, que está desconectada ponta a ponta, não só aqui.

**Bug latente (não corrigido — código inalcançável em produção hoje):** `dispatch()` captura
apenas `httpx.RequestError`, mas `resp.raise_for_status()` levanta `httpx.HTTPStatusError`, que
herda de `httpx.HTTPError` e não de `RequestError`. Uma resposta 4xx/5xx do receptor do webhook
propagaria como exceção não tratada em vez de retornar `{"success": False, ...}`. Registrado aqui
para quem for religar este dispatcher no futuro — não corrigido agora porque não há teste (nem
caminho de execução real) que o exercite; corrigir sem religar seria código morto testado por
suposição, não por comportamento observado.
