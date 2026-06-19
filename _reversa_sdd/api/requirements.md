# API — Interface REST + WebSocket

> Gerado pelo Writer — 2026-06-19
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Visão Geral

Camada de entrada do sistema. Expõe API REST para gerenciamento de PBXs, WebSocket para agent assist em tempo real, autenticação JWT com RBAC, rate limiting e webhooks pós-chamada.

## Responsabilidades

- Autenticação e autorização via JWT com papéis (agent, tenant_admin)
- Rate limiting in-memory (100 req/60s por IP)
- CRUD de PBXs por tenant (`/api/v1/admin/pbxs`)
- Gerenciamento de conexões WebSocket para agent assist
- Auto-link de ramal SIP via IP do WebSocket
- Linkage manual via código *88
- Disparo de webhooks pós-chamada
- Health check endpoints (`/health`, `/ready`)

## Regras de Negócio

- Apenas `tenant_admin` pode criar/listar PBXs 🟢
- Rate limit: 100 requisições por IP a cada 60 segundos 🟢
- Auto-link de ramal SIP via IP do WebSocket (consulta Redis `zenith:sip:ip_to_extension`) 🟢
- Linkage manual via *88 com TTL de 120s para sessão 🟢
- JWT expira em 60 minutos 🟢
- Token JWT contém: sub, tenant_id, role, exp, iat 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Gerar token JWT com subject, tenant_id, role | Must | `create_access_token()` retorna string JWT válida |
| RF-02 | Verificar token JWT em endpoints protegidos | Must | `verify_token()` retorna payload ou 401 |
| RF-03 | Restringir endpoints admin a tenant_admin | Must | `require_admin_role()` retorna 403 se role != tenant_admin |
| RF-04 | Limitar requisições a 100/IP/60s | Must | 101ª requisição em 60s retorna 429 |
| RF-05 | Criar PBX vinculado a tenant | Must | POST `/api/v1/admin/pbxs` retorna 201 com PBXResponse |
| RF-06 | Listar PBXs do tenant autenticado | Must | GET `/api/v1/admin/pbxs` retorna lista |
| RF-07 | Aceitar conexão WebSocket por call_id | Must | WS conectado envia eventos em tempo real |
| RF-08 | Auto-link de ramal SIP via IP | Should | Ao conectar WS, busca IP → extension no Redis |
| RF-09 | Linkage manual via *88 | Should | Cria sessão "awaiting_linkage" por 120s |
| RF-10 | Disparar webhooks pós-chamada | Should | Payload montado e enviado para URL configurada |
| RF-11 | Expor health checks | Must | `/health` e `/ready` retornam 200 |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Performance | Rate limit de 100 req/60s por IP | `rate_limit.py:7-8` | 🟢 |
| Segurança | JWT obrigatório em endpoints protegidos | `auth.py:22-30` | 🟢 |
| Segurança | RBAC com role tenant_admin para operações admin | `auth.py:35-40` | 🟢 |
| Disponibilidade | Sessão WebSocket com heartbeat implícito | `websockets.py:33-38` | 🟡 |
| Disponibilidade | Linkage manual expira em 120s (TTL) | `websockets.py:95-97` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um agente autenticado com role "agent"
Quando acessa POST /api/v1/admin/pbxs
Então recebe 403 Forbidden

Dado um admin autenticado com role "tenant_admin"
Quando envia POST /api/v1/admin/pbxs com {name, host, port}
Então recebe 201 Created com PBXResponse

Dado um cliente IP que já fez 100 requisições nos últimos 60s
Quando faz a 101ª requisição
Então recebe 429 Too Many Requests

Dado uma conexão WebSocket estabelecida
Quando o IP do cliente tem ramal SIP mapeado no Redis
Então a sessão é vinculada automaticamente (auto-link)
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Autenticação JWT | Must | Caminho crítico, toda requisição depende |
| CRUD de PBXs | Must | Funcionalidade core do admin |
| WebSocket Agent Assist | Must | Principal interface com operador |
| Rate limiting | Should | Proteção contra abuso, sem ele o sistema ainda funciona |
| Auto-link SIP | Should | Conveniência, linkage manual é fallback |
| Webhooks | Could | Pós-chamada, sem consumidor claro no código |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `src/api/auth.py` | `create_access_token`, `verify_token`, `require_admin_role` | 🟢 |
| `src/api/rate_limit.py` | `rate_limit_middleware` | 🟢 |
| `src/api/routers/pbxs.py` | `create_pbx`, `list_pbxs` | 🟢 |
| `src/api/websockets.py` | `AgentAssistWebSocket` | 🟢 |
| `src/api/webhooks.py` | `WebhookDispatcher` | 🟢 |
