# Matriz de Permissões — zenith-voip

> Gerado pelo Detective — 2026-06-19
> **Re-extração incremental — 2026-07-27** (deltas D-02/D-07)
> Confiança: 🟢 CONFIRMADO

## Papéis

| Papel | Identificador | Descrição |
|-------|---------------|-----------|
| Agente | `agent` | Operador de call center, acessa o widget e participa de chamadas |
| Admin do Tenant | `tenant_admin` | Administrador do inquilino, gerencia PBXs e configurações |

**Nota:** O sistema não possui um papel de super-admin (cross-tenant). A gestão de tenants é feita externamente (via migrations ou admin direto no DB).

## Matriz de Permissões

| Funcionalidade | agent | tenant_admin | Origem |
|----------------|-------|-------------|--------|
| Criar PBX | ❌ | ✅ | `auth.py:35-40` |
| Listar PBXs | ❌ | ✅ | `auth.py:35-40` |
| Gerar token JWT | ✅ (role=agent) | ✅ (role=tenant_admin) | `auth.py:10-18` |
| Acessar WebSocket | ✅ | ✅ | `websockets.py:3` |
| Receber transcrições | ✅ | ✅ | `websockets.py:112-118` |
| Receber alertas | ✅ | ✅ | `websockets.py:99-110` |
| Linkage manual (*88) | ✅ | ✅ | `websockets.py:78-97` |
| Acessar /health e /ready | ✅ | ✅ | `main.py:46-53` |
| Acessar /metrics | ✅ | ✅ | `telemetry.py:58-60` |
| 🆕 Abrir `/audio-stream/{call_id}` | — | — | somente o FreeSWITCH, ver abaixo |

## Autorização do stream de áudio 🆕

O endpoint `/audio-stream/{call_id}` **não usa JWT**. Quem se conecta a ele é o próprio
FreeSWITCH, via `uuid_audio_stream`, sem carregar credencial de usuário. A autorização é
feita por **posse de um `call_id` registrado**:

```
CHANNEL_ANSWER (ESL) → register_stream_metadata(call_id, ...) → call_id vira autorizado
WebSocket em /audio-stream/{call_id} → call_id ausente de stream_metadata → close(4401)
```

Três camadas sustentam isso:

| Camada | Proteção |
|---|---|
| Guard do `AudioIngestor` | Só aceita `call_id` que veio de um `CHANNEL_ANSWER` real (`ingestor.py:27-36`) |
| Bind de rede | Portas 8001/8002 publicadas apenas em `127.0.0.1` — inalcançáveis de fora do host |
| Ciclo de vida | `stream_metadata` é limpo no `finally` do handler; a autorização expira com a chamada |

**Antes de 2026-07-12** nenhuma dessas camadas existia: qualquer conexão WebSocket com um
`call_id` inventado era aceita e bufferizada como se fosse chamada real, num endpoint
publicado em `0.0.0.0`.

🔴 **Limite conhecido:** a autorização é por *conhecimento* do `call_id`, não por
autenticação. Um processo local que consiga adivinhar ou observar um `call_id` ativo pode se
conectar dentro da janela da chamada. A mitigação real hoje é o bind em loopback.

## Mecanismo de Autenticação

1. Cliente obtém token JWT via endpoint externo (não implementado no código — token é gerado programaticamente por `create_access_token()`)
2. Token contém: `sub`, `tenant_id`, `role`, `exp`, `iat`
3. Endpoints protegidos usam `verify_token()` → decodifica JWT
4. `require_admin_role()` → verifica `role == "tenant_admin"`, senão 403

## Escopo de Dados

- Cada tenant vê **apenas seus próprios dados** (filtrando por `tenant_id` no payload JWT)
- Isolamento físico via schema PostgreSQL separado por tenant (multitenancy)
- O escopo cross-tenant não é suportado pela API atual
