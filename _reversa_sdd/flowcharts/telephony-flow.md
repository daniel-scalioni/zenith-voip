# Fluxograma — Módulo Telephony

> Atualizado na re-extração incremental de **2026-07-27** (deltas D-01/D-12)

## Arquitetura de conexões ESL 🆕

```mermaid
flowchart LR
    subgraph ESLClient
        A[Conexão de eventos<br/>reader/writer]
        B[Conexão de comandos<br/>_cmd_reader/_cmd_writer<br/>serializada por _cmd_lock]
    end
    FS[(FreeSWITCH<br/>mod_event_socket :8021)]
    A -->|subscribe json all| FS
    B -->|api / bgapi| FS
    FS -->|event stream| A
    FS -->|resposta de comando| B
```

> Antes as duas funções dividiam o mesmo socket: um `bgapi` disparado de dentro de um
> handler de evento competia pela leitura com o event loop, e a resposta podia se misturar
> ao evento seguinte e se perder.

## Event Loop ESL

```mermaid
flowchart TD
    A[start_event_listener] --> B[_event_loop]
    B --> C{Conectado?}
    C -->|Não| D[connect: consome auth/request<br/>→ auth → subscribe json]
    D --> B
    C -->|Sim| E[_read_events: read 65536<br/>timeout 300s]
    E --> E2{Buffer tem headers<br/>+ Content-Length bytes?}
    E2 -->|Não| E
    E2 -->|Sim| F[Extrai corpo exato<br/>e decodifica JSON]
    F --> G{Roteia por Event-Name}
    G -->|SOFIA_REGISTER| H[_handle_register]
    G -->|SOFIA_UNREGISTER| I[_handle_unregister]
    G -->|CHANNEL_CREATE| J{*88?}
    J -->|Sim| K[manual linkage broadcast]
    J -->|Não| L[Ignora]
    G -->|CHANNEL_ANSWER| M[_handle_channel_answer]
    G -->|CHANNEL_HANGUP| N[_handle_channel_hangup]
    H --> O[Cache SIP mapping Redis TTL 3600s]
    I --> P[Remove SIP mapping Redis]
    F -.->|exceção no handler| Q[logger.exception<br/>event loop continua]
```

## CHANNEL_ANSWER — início da gravação 🆕

```mermaid
flowchart TD
    A[CHANNEL_ANSWER] --> B[Lê variable_zenith_tenant_id / pbx_id / agent_extension]
    B --> C[audio_ingestor.register_stream_metadata<br/>= autoriza o WebSocket desse call_id]
    C --> D{tenant_id populado?}
    D -->|Não| E[Encerra: sem Call, sem captura]
    D -->|Sim| F[create_call_record<br/>status=in_progress, direction=inbound]
    F --> G[_start_audio_capture]
    G --> H["bgapi uuid_audio_stream {call_id} start<br/>ws://AUDIO_STREAM_CALLBACK_HOST/audio-stream/{call_id}<br/>stereo 8k {metadata}"]
    H --> I{Resposta tem +OK?}
    I -->|Não| J[logger.warning — captura não iniciou]
    I -->|Sim| K[FreeSWITCH abre WS → AudioIngestor]
```

## CHANNEL_HANGUP — fechamento e gravação 🆕

```mermaid
flowchart TD
    A[CHANNEL_HANGUP] --> B{tenant_id populado?}
    B -->|Sim| C[finalize_call_record<br/>status=completed, ended_at, duration_seconds]
    B -->|Não| D[Pula persistência]
    C --> E[buffers.pop call_id]
    D --> E
    E --> F{Há chunks?}
    F -->|Não| G[Fim — nada a gravar]
    F -->|Sim| H[Agrupa chunks por canal tx/rx]
    H --> I[enqueue_recording_upload<br/>→ fila arq upload_recording_batch]
    I --> J[zenith-arq-uploader grava .raw → mp3]
```

## Reconexão Automática

```mermaid
flowchart TD
    A[Event Loop] --> B{Erro de conexão / EOF?}
    B -->|Sim| C[connected = false]
    C --> D[Aguardar 2s]
    D --> E[Tentar reconnect]
    E --> F{Sucesso?}
    F -->|Sim| B
    F -->|Não| D
```

> O timeout de leitura subiu de 30 s para **300 s**: o FreeSWITCH não manda heartbeat em
> conexão ociosa, e o timeout curto derrubava a conexão a cada janela sem chamada, criando
> um gap onde um `CHANNEL_ANSWER` real podia chegar e se perder.

## Caminho da chamada no dialplan 🔄

```mermaid
flowchart TD
    A[Chamada entra] --> B{destination_number}
    B -->|9196| C[echo_test: answer + echo]
    B -->|1XXX| D[local_extension: bridge user/$1@zenith.local]
    B -->|demais dígitos| E[zenith_audio_fork]
    E --> F["set zenith_call_id / tenant_id / pbx_id / agent_extension<br/>(tenant e pbx vêm de $$ globais do vars.xml)"]
    F --> G[answer + start_dtmf]
    G --> H["bridge sofia/gateway/upstream-{sip_from_user}/{destination_number}"]
    H --> I[CHANNEL_ANSWER → ESLClient dispara a captura]
```

> A captura de áudio **não é mais uma ação do dialplan**. `mod_audio_fork` saiu; o
> `uuid_audio_stream` é disparado pela aplicação, via ESL, depois do `CHANNEL_ANSWER`.
