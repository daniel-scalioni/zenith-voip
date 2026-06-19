# Legacy Impact: Alta Escala, Isolamento Multitenant e PBX Múltiplos

> Identificador: `002-escala-eventos`
> Data: `2026-05-21`

## Arquivos afetados

| Arquivo afetado | Componente (specs/) | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `src/database/models.py` | architecture-guide.md#modelos | regra-alterada | CRITICAL | `tenant_id` removido de Call, adicionado `pbx_id` e `agent_sip_extension`. Modelos migrados para `TenantBase` (schema por tenant). |
| `src/database/database.py` | architecture-guide.md#database | regra-alterada | CRITICAL | Adicionado Database Router multi-schema com `search_path` dinâmico e `create_tenant_schema()`. |
| `alembic/env.py` | architecture-guide.md#database | regra-alterada | HIGH | Suporte a migração por schema via `SCHEMA_NAME`. |
| `src/telephony/esl_client.py` | architecture-guide.md#telephony | regra-alterada | CRITICAL | Adicionado event listener ESL para SIP REGISTER/INVITE, cache Redis, *88 manual linkage. |
| `src/api/websockets.py` | architecture-guide.md#websocket | regra-alterada | HIGH | Adicionado IP matching automático no handshake + eventos session_linked/session_waiting_linkage. |
| `src/audio/ingestor.py` | architecture-guide.md#audio | regra-alterada | HIGH | Metadados tenant/pbx/agent_extension nos eventos do Redis Streams. |
| `freeswitch/conf/dialplan/default.xml` | architecture-guide.md#freeswitch | regra-alterada | HIGH | Registration Forwarding + *88 fallback + variáveis de tenant/PBX no audio fork. |
| `src/api/auth.py` | architecture-guide.md#auth | regra-alterada | MEDIUM | JWT agora inclui tenant_id e role (tenant_admin/agent). |
| `src/api/routers/pbxs.py` | - | componente-novo | MEDIUM | Novo router REST para gerenciamento de PBXs. |
| `src/workers/audio_uploader.py` | - | componente-novo | LOW | Worker ARQ para upload S3 isolado por tenant. |
| `src/utils/telemetry.py` | - | componente-novo | LOW | Métricas Prometheus multi-schema e Redis Streams. |
| `tests/test_multitenancy.py` | - | componente-novo | MEDIUM | Testes de integração de schemas multi-tenant. |
| `tests/test_telephony_matching.py` | - | componente-novo | MEDIUM | Testes de WebSocket handshake e eventos. |

## Diff conceitual por componente

### Database Layer
- **Antes**: Database SQLAlchemy simples, tabelas em `public`, `tenant_id` como coluna opcional em `calls`.
- **Depois**: Database Router com `search_path` dinâmico. Tabelas de negócio migradas para schemas dedicados `tenant_<uuid>`. Tabelas administrativas (`tenants`, `pbxs`) permanecem em `public`.

### Telephony ESL
- **Antes**: ESLClient apenas conectava e enviava comandos. Sem escuta de eventos.
- **Depois**: ESLClient mantém event listener assíncrono contínuo, processa SOFIA_REGISTER/SOFIA_UNREGISTER/CHANNEL_CREATE/CHANNEL_ANSWER, salva mapeamentos no Redis.

### WebSocket Agent Assist
- **Antes**: Aceitava conexões por call_id, broadcast de transcrições.
- **Depois**: Handshake faz IP matching automático contra Redis. Envia session_linked/session_waiting_linkage. Aceita upstream `manual_linkage_request`.

### FreeSWITCH Dialplan
- **Antes**: Bypass/audio_fork/filler simples.
- **Depois**: Registration Forwarding (proxy transparente), variáveis de tenant/pbx injectadas, extensão *88 para pareamento manual.

## Preservadas

- 🟢 `specs/architecture-guide.md#6-barramento-de-eventos-redis-streams` — Redis Streams mantido como barramento unificado, agora com metadados adicionais.
- 🟢 `specs/architecture-guide.md#3-strategy-pattern-para-servicos` — Strategy pattern STT/TTS/LLM intacto.
- 🟢 `specs/architecture-guide.md#5-async-do-comeco-ao-fim` — Toda lógica pesada permanece assíncrona via ARQ workers.
- 🟢 Estrutura de containers Docker (FreeSWITCH, Redis, PostgreSQL, Ollama, Piper) preservada.

## Modificadas

- 🟢 **Isolamento de Dados**: RN-02 alterada de isolamento lógico (coluna tenant_id) para isolamento físico (schema por tenant).
- 🟢 **Rastreamento SIP**: RN-01 nova — rastreamento dinâmico de ramais via interceptação SIP + Redis.
- 🟢 **Múltiplos PBXs**: RN-03 nova — suporte a múltiplos PBXs por cliente.
- 🟢 **Auth JWT**: Agora inclui `tenant_id` e `role` para autorização multi-tenant.
