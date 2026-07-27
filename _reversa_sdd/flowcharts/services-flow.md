# Fluxograma — Módulo Services

> Atualizado na re-extração incremental de **2026-07-27** (deltas D-05/D-09)

## Ciclo de vida da entidade Call (calls.py) 🆕

```mermaid
flowchart TD
    A[CHANNEL_ANSWER com tenant_id] --> B["get_tenant_db(tenant_&lt;id&gt;)"]
    B --> C[Repository Call .create<br/>direction=inbound, status=in_progress]
    C --> D[conn.commit explícito]
    D --> E[...chamada em curso...]
    E --> F[CHANNEL_HANGUP]
    F --> G[find_by call_id]
    G --> H{Encontrou?}
    H -->|Não| I[Retorna em silêncio]
    H -->|Sim| J[update: status=completed<br/>ended_at=now, duration=ended-started]
```

## AutoFallback STT

```mermaid
flowchart TD
    A[transcribe: audio_chunk] --> B[Tenta DeepgramSTT com timeout 500ms]
    B --> C{Sucesso?}
    C -->|Sim| D{confidence > 0.3?}
    D -->|Sim| E[Retorna resultado primary]
    C -->|Não| F[Fallback WhisperCppSTT]
    D -->|Não| F
    F --> G[Retorna resultado fallback]
    G --> H[marca fallback_activated=true]
    E --> I[fallback_activated=false]
```

## TTS com Fallback 🔄

```mermaid
flowchart TD
    A[synthesize: text] --> B[PiperTTS.synthesize]
    B --> C[asyncio.to_thread — não bloqueia o event loop]
    C --> D{Modelo já em cache?}
    D -->|Não| E["PiperVoice.load(PIPER_VOICE_PATH)<br/>lru_cache maxsize=1"]
    D -->|Sim| F[Reusa modelo carregado]
    E --> F
    F --> G[synthesize_wav → io.BytesIO]
    G --> H{Sucesso?}
    H -->|Sim| I[Retorna WAV sintetizado]
    H -->|Não| J[Carrega WAV local do disco]
    J --> K[Retorna áudio fallback]
```

> O TTS deixou de ser uma chamada HTTP a um microserviço (`http://piper-tts:5000/synthesize`)
> e passou a rodar **no próprio processo FastAPI**. O container `piper-tts` foi removido.
> Os parâmetros `voice` e `speaker_id` continuam na assinatura mas são ignorados — a voz
> vem de `PIPER_VOICE_PATH`.
