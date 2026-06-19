# Módulo: api

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO (leitura direta do código)

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/api/auth.py` | Autenticação JWT + RBAC | 41 |
| `src/api/rate_limit.py` | Rate limiting por IP (in-memory) | 27 |
| `src/api/routers/pbxs.py` | CRUD de PBXs | 82 |
| `src/api/webhooks.py` | Dispatcher de webhooks | 36 |
| `src/api/websockets.py` | WebSocket para agent assist | 121 |

## Fluxo de Controle

### auth.py
- `create_access_token()` → gera JWT com subject, tenant_id, role, exp, iat
- `verify_token()` → decodifica JWT, retorna payload ou 401
- `require_admin_role()` → verifica role == "tenant_admin" ou 403

### rate_limit.py
- Middleware que conta requisições por IP em janela de 60s (100 req/min)
- Usa `defaultdict(list)` in-memory (sem persistência)

### routers/pbxs.py
- `POST /api/v1/admin/pbxs` → cria PBX vinculado a tenant (requer admin)
- `GET /api/v1/admin/pbxs` → lista PBXs do tenant autenticado
- Ambos usam `require_admin_role` + `get_db` como dependências

### websockets.py
- `AgentAssistWebSocket` gerencia conexões WebSocket por call_id
- `connect()` → aceita WS, tenta auto-link por IP (consulta Redis)
- `_try_auto_link()` → busca extension no Redis por IP; se não achar, enfileira linkage manual
- `handle_transcript()` → extrai entidades via RegexExtractor, broadcast
- `handle_alert()` → dispara alertas de anomalia
- `_on_manual_linkage_request()` → cria sessão Redis "awaiting_linkage" com TTL 120s

### webhooks.py
- `WebhookDispatcher` → dispatcher HTTP genérico com suporte a signature header
- `dispatch_post_call()` → monta payload pós-chamada e envia

## Algoritmos

**Auto-link SIP**: Ao conectar WebSocket, o IP do cliente é usado como chave para buscar o ramal SIP no Redis (`zenith:sip:ip_to_extension:{ip}`). Se encontrado, a sessão é vinculada automaticamente. Caso contrário, o agente precisa discar *88 para vincular.

## Estruturas de Dados

### auth.py
- Payload JWT: `{ sub, tenant_id, role, exp, iat }`

### rate_limit.py
- `rate_limit_store: dict[str, list[float]]` — IP → timestamps

### routers/pbxs.py
- `PBXCreate`: name, host, port
- `PBXResponse`: id, tenant_id, name, host, port, created_at

### websockets.py
- `active_connections: dict[str, list[WebSocket]]` — call_id → conexões

## Configurações

| Constante | Valor | Local |
|-----------|-------|-------|
| RATE_LIMIT_REQUESTS | 100 | rate_limit.py |
| RATE_LIMIT_WINDOW | 60 (s) | rate_limit.py |
| JWT_EXPIRATION_MINUTES | 60 | config.py |
| JWT_ALGORITHM | HS256 | config.py |
| WS_AGENT_SESSION_TTL | 30 | esl_client.py |

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Apenas tenant_admin pode criar/listar PBXs | `auth.py:35-40` | 🟢 |
| Rate limit: 100 req/60s por IP | `rate_limit.py:7-8` | 🟢 |
| Auto-link de ramal via IP do WebSocket | `websockets.py:33-56` | 🟢 |
| Linkage manual via *88 com TTL 120s | `websockets.py:81-97` | 🟢 |
