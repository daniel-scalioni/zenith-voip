# Fluxograma — Módulo API

> Atualizado na re-extração incremental de **2026-07-27** (delta D-07)

## Ciclo de vida da aplicação (main.py) 🆕

```mermaid
flowchart TD
    A[Startup FastAPI] --> B[logging.basicConfig LOG_LEVEL]
    B --> C[init_db]
    C --> D{INSTANCE_ID == 1?}
    D -->|Sim| E[esl_client.start_event_listener<br/>= único consumidor do event stream]
    D -->|Não| F[Instância serve só HTTP/WS de negócio]
    E --> G[yield — app servindo]
    F --> G
    G --> H[Shutdown]
    H --> I{INSTANCE_ID == 1?}
    I -->|Sim| J[esl_client.close]
```

> Antes desta mudança o `esl_client` **nunca era conectado**: os handlers de evento existiam
> mas jamais executavam. O acoplamento a `INSTANCE_ID == 1` existe porque
> `create_call_record()` não é idempotente — e torna `fastapi-1` ponto único de falha para
> a captura de áudio (🟡 risco arquitetural aberto).

## WebSocket de áudio (`/audio-stream/{call_id}`) 🆕

```mermaid
flowchart TD
    A[FreeSWITCH conecta via uuid_audio_stream] --> B{call_id em stream_metadata?}
    B -->|Não| C[close 4401 — sem accept]
    B -->|Sim| D[accept]
    D --> E[receive]
    E --> F{Tipo do frame}
    F -->|disconnect| G[WebSocketDisconnect → limpa estado]
    F -->|texto JSON de controle| E
    F -->|bytes| H[_split_stereo_frame → tx, rx]
    H --> I[Buffer + publish por canal no Redis Stream]
    I --> E
```

## Fluxo de Autenticação (auth.py)

```mermaid
flowchart TD
    A[Cliente envia requisição] --> B{Token JWT presente?}
    B -->|Não| C[401 Unauthorized]
    B -->|Sim| D[verify_token: decodifica JWT]
    D --> E{Token válido?}
    E -->|Não| F[401 Unauthorized]
    E -->|Sim| G[require_admin_role: role == tenant_admin?]
    G -->|Não| H[403 Forbidden]
    G -->|Sim| I[Payload retornado para o handler]
```

## Fluxo de Auto-Link (websockets.py)

```mermaid
flowchart TD
    A[WebSocket connect] --> B[Aceitar conexão]
    B --> C[Registrar em active_connections]
    C --> D[Buscar IP do cliente]
    D --> E[Redis: ip_to_extension?]
    E -->|Encontrado| F[Broadcast session_linked]
    E -->|Não encontrado| G[Broadcast session_waiting_linkage]
    G --> H[Agente disca *88]
    H --> I[Redis: criar sessão awaiting_linkage TTL 120s]
```

## Fluxo de Rate Limit (rate_limit.py)

```mermaid
flowchart TD
    A[Requisição chega] --> B[Extrair IP do cliente]
    B --> C[Limpar timestamps expirados]
    C --> D{Contagem > 100?}
    D -->|Sim| E[429 Too Many Requests]
    D -->|Não| F[Adicionar timestamp atual]
    F --> G[Passar para próxima middleware/rota]
```
