# Módulo: api

> Gerado pelo Archaeologist — 2026-06-19
> **Re-extração incremental — 2026-07-27** (base `48da5b1` → `0658157`, delta D-07)
> Confiança: 🟢 CONFIRMADO (leitura direta do código)

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/main.py` | App FastAPI, lifespan, endpoint de áudio | 58 |
| `src/api/auth.py` | Autenticação JWT + RBAC | 41 |
| `src/api/rate_limit.py` | Rate limiting por IP (in-memory) | 27 |
| `src/api/routers/pbxs.py` | CRUD de PBXs | 82 |
| `src/api/webhooks.py` | Dispatcher de webhooks | 36 |
| `src/api/websockets.py` | WebSocket para agent assist | 121 |

## Fluxo de Controle

### main.py 🆕 (mudança estruturante)

- `logging.basicConfig(level=settings.LOG_LEVEL, ...)` global no import do módulo.
- **`lifespan`** passou a iniciar o ESL:
  ```python
  if settings.INSTANCE_ID == 1:
      await esl_client.start_event_listener()
  ```
  Na extração anterior, `esl_client` **nunca era conectado em lugar nenhum** — os handlers
  `CHANNEL_ANSWER`/`CHANNEL_HANGUP` existiam mas jamais rodavam, e
  `register_stream_metadata()` nunca populava `audio_ingestor.stream_metadata` para chamadas
  reais. Esse era o gap que impedia todo o pipeline de gravação de funcionar.
- **Só a instância 1 conecta**: `create_call_record()` não é idempotente, e duas instâncias
  processando o mesmo evento criariam linhas `Call` duplicadas. Isso torna `fastapi-1` um
  **ponto único de falha para captura** — 🟡 se ela cair, `fastapi-2` continua servindo HTTP
  mas nenhuma chamada é gravada.
- 🆕 Endpoint `@app.websocket("/audio-stream/{call_id}")` → delega a
  `audio_ingestor.handle_forked_stream(call_id, websocket)`. É o destino do
  `uuid_audio_stream` disparado pelo `ESLClient` (`AUDIO_STREAM_CALLBACK_HOST`).

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
| 🆕 Apenas `INSTANCE_ID == 1` consome o event stream do ESL | `main.py:26,34` | 🟢 |
| 🆕 `/audio-stream/{call_id}` exige `call_id` registrado via ESL (fecha 4401) | `audio/ingestor.py:27-36` | 🟢 |

## Superfície de rede

| Endpoint | Exposição |
|---|---|
| `fastapi-1` :8000 | publicado em **`127.0.0.1:8001`** (antes `0.0.0.0:8001`) |
| `fastapi-2` :8000 | publicado em **`127.0.0.1:8002`** (antes `0.0.0.0:8002`) |
| `bunkerweb` | 80/443 — proxy reverso público com sticky session |

O fechamento das portas 8001/8002 no host (2026-07) é o que impede que o endpoint
`/audio-stream/{call_id}` seja alcançável de fora da máquina.
