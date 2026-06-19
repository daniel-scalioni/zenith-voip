# API, Design Técnico

> Gerado pelo Writer — 2026-06-19
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Interface

### Endpoints HTTP

| Método | Caminho | Entrada | Saída | Status codes |
|--------|---------|---------|-------|--------------|
| GET | `/health` | - | `{"status": "ok"}` | 200 |
| GET | `/ready` | - | `{"status": "ready"}` | 200 |
| POST | `/api/v1/admin/pbxs` | `PBXCreate` | `PBXResponse` | 201, 400, 403, 409 |
| GET | `/api/v1/admin/pbxs` | - | `List[PBXResponse]` | 200, 403 |

### WebSocket

| Caminho | Protocolo | Payloads |
|---------|-----------|----------|
| `/ws/{call_id}` | JSON sobre WSS | transcript, alert, insight, status |

### Funções Core

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `create_access_token` | `(subject: str, tenant_id: str, role: str, expires_delta: timedelta)` | `str` (JWT) | Gera token HS256 com claims sub, tenant_id, role, exp, iat |
| `verify_token` | `(credentials: HTTPAuthorizationCredentials)` | `dict` (payload) | Decodifica JWT, retorna payload ou HTTPException 401 |
| `require_admin_role` | `(payload: dict = Depends(verify_token))` | `dict` (payload) | Verifica role == "tenant_admin", senão HTTPException 403 |
| `create_pbx` | `(data: PBXCreate, payload: dict, db: AsyncSession)` | `PBXResponse` | Insere PBX com tenant_id do payload |
| `list_pbxs` | `(payload: dict, db: AsyncSession)` | `List[PBXResponse]` | Filtra por tenant_id do payload |

### DTOs

| DTO | Campos |
|-----|--------|
| `PBXCreate` | `name: str (max 128)`, `host: str (max 128)`, `port: int (default 5060, 1-65535)` |
| `PBXResponse` | `id: str`, `tenant_id: str`, `name: str`, `host: str`, `port: int`, `created_at: str` |

## Fluxo Principal

1. Cliente autentica e obtém JWT via `create_access_token()` — `src/api/auth.py:10-18`
2. Requisições REST passam por `verify_token()` e opcionalmente `require_admin_role()` — `src/api/auth.py:22-40`
3. Rate limit checa IP em `rate_limit_store` (dict in-memory) — `src/api/rate_limit.py:5-12`
4. Admin cria/lista PBXs via `/api/v1/admin/pbxs` — `src/api/routers/pbxs.py:15-72`
5. Operador conecta WebSocket em `/ws/{call_id}` — `src/api/websockets.py:33-38`
6. Sistema tenta auto-link: IP → Redis `zenith:sip:ip_to_extension:{ip}` — `src/api/websockets.py:40-56`
7. Se auto-link falha, aguarda *88 para linkage manual (TTL 120s) — `src/api/websockets.py:78-97`
8. Eventos de transcrição e alertas são broadcast para todas as conexões do call_id — `src/api/websockets.py:99-118`
9. Após chamada, webhooks são disparados via `WebhookDispatcher` — `src/api/webhooks.py:15-36`

## Fluxos Alternativos

- **Auto-link falha:** aguarda linkage manual via *88 com TTL de 120s; se expirar, sessão permanece sem vinculação
- **Rate limit excedido:** middleware retorna 429 sem processar a requisição
- **Token expirado/inválido:** `verify_token()` retorna 401 Unauthorized
- **Role inválida:** `require_admin_role()` retorna 403 Forbidden
- **PBX duplicado:** nome duplicado no mesmo tenant retorna 409 Conflict

## Dependências

- `database` — sessão AsyncSession via `get_db()` para operações CRUD 🟢
- `events` — publicação de eventos no Redis Stream após criação/alteração de PBX 🟡
- `extraction` — `RegexExtractor` usado no WebSocket para extrair entidades de transcrições 🟢
- `telephony` — mapeamento SIP/IP no Redis para auto-link 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Rate limit in-memory (sem Redis) | `rate_limit.py:5` — defaultdict(list) | 🟢 |
| JWT com HS256 e segredo em config | `config.py:20-23` | 🟢 |
| Auto-link SIP via Redis lookup por IP | `websockets.py:40-56` | 🟢 |
| Sessão WebSocket com TTL 30-120s no Redis | `esl_client.py:179-184` | 🟢 |

## Estado Interno

- `rate_limit_store: dict[str, list[float]]` — IP → timestamps de requisições (in-memory, volátil)
- `active_connections: dict[str, list[WebSocket]]` — call_id → conexões WebSocket ativas
- Sessões Redis: `zenith:ws:agent_session:{uuid}` (TTL 30-120s), `zenith:sip:*` (TTL 3600s)

## Observabilidade

- Métricas: `prometheus-client` exporta métricas via `/metrics` (16 métricas) — `src/observability/telemetry.py`
- Tracing: OpenTelemetry instrumenta FastAPI — `src/observability/telemetry.py`
- Logs: via `pino` (estruturado), nível configurável por `LOG_LEVEL`

## Riscos e Lacunas

- 🔴 Rate limit in-memory: reinicialização da instância zera o contador — permite burst após restart
- 🟡 Webhook dispatcher sem confirmação de entrega (fire-and-forget)
- 🟡 Auto-link SIP depende de Redis populado pelo ESL Client — sem fallback se Redis vazio
