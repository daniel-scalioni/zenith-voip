# Dicionário de Dados — zenith-voip

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## 1. Banco de Dados (PostgreSQL)

### Schema: public

#### tenants
| Campo | Tipo | Obrigatório | PK/FK | Default | Descrição |
|-------|------|-------------|-------|---------|-----------|
| id | UUID | sim | PK | gen_random_uuid() | ID do tenant |
| name | VARCHAR(128) | sim | - | - | Nome do inquilino |
| schema_name | VARCHAR(64) | sim | UQ | - | Nome do schema PostgreSQL |
| status | VARCHAR(32) | não | - | 'active' | Status do tenant |
| created_at | TIMESTAMPTZ | não | - | now() | Data de criação |
| updated_at | TIMESTAMPTZ | não | - | now() | Data de atualização |

#### pbxs
| Campo | Tipo | Obrigatório | PK/FK | Default | Descrição |
|-------|------|-------------|-------|---------|-----------|
| id | UUID | sim | PK | gen_random_uuid() | ID do PBX |
| tenant_id | UUID | sim | FK→tenants.id | - | ID do tenant (CASCADE) |
| name | VARCHAR(128) | sim | - | - | Nome do PBX |
| host | VARCHAR(128) | sim | - | - | Host/IP do PBX |
| port | INTEGER | não | - | 5060 | Porta SIP |
| created_at | TIMESTAMPTZ | não | - | now() | Data de criação |
| updated_at | TIMESTAMPTZ | não | - | now() | Data de atualização |

### Schema: tenant_{id}

#### calls
| Campo | Tipo | Obrigatório | PK/FK | Default | Descrição |
|-------|------|-------------|-------|---------|-----------|
| id | UUID | sim | PK | uuid4 | ID interno |
| call_id | VARCHAR(128) | sim | UQ, IDX | - | ID externo da chamada |
| agent_uuid | VARCHAR(128) | não | - | - | UUID do agente no FS |
| customer_uuid | VARCHAR(128) | não | - | - | UUID do cliente no FS |
| pbx_id | UUID | não | - | - | ID do PBX |
| agent_sip_extension | VARCHAR(64) | não | - | - | Ramal SIP do agente |
| direction | VARCHAR(16) | sim | - | - | inbound/outbound |
| status | VARCHAR(32) | não | - | 'in_progress' | ringing/in_progress/completed/failed |
| caller_number | VARCHAR(32) | não | - | - | Número do chamador |
| callee_number | VARCHAR(32) | não | - | - | Número do destino |
| started_at | TIMESTAMPTZ | não | - | now() | Início da chamada |
| ended_at | TIMESTAMPTZ | não | - | - | Fim da chamada |
| duration_seconds | FLOAT | não | - | - | Duração em segundos |
| metadata | JSONB | não | - | - | Metadados extras |
| created_at | TIMESTAMPTZ | não | - | now() | Data de criação |
| updated_at | TIMESTAMPTZ | não | - | now() | Data de atualização |

#### transcripts
| Campo | Tipo | Obrigatório | PK/FK | Default | Descrição |
|-------|------|-------------|-------|---------|-----------|
| id | UUID | sim | PK | uuid4 | ID interno |
| call_id | UUID | sim | FK→calls.id (CASCADE) | - | ID da chamada |
| channel | VARCHAR(16) | sim | - | - | Canal (tx/rx) |
| speaker | VARCHAR(64) | não | - | - | Identificador do falante |
| text | TEXT | sim | - | - | Texto transcrito |
| confidence | FLOAT | não | - | - | Confiança da transcrição |
| start_time | FLOAT | sim | - | - | Início do segmento (s) |
| end_time | FLOAT | sim | - | - | Fim do segmento (s) |
| is_final | BOOLEAN | não | - | true | Se é transcrição final |
| metadata | JSONB | não | - | - | Metadados extras |
| created_at | TIMESTAMPTZ | não | - | now() | Data de criação |

#### call_insights
| Campo | Tipo | Obrigatório | PK/FK | Default | Descrição |
|-------|------|-------------|-------|---------|-----------|
| id | UUID | sim | PK | uuid4 | ID interno |
| call_id | UUID | sim | FK→calls.id (CASCADE) | - | ID da chamada |
| sentiment | VARCHAR(32) | não | - | - | Sentimento (positive/neutral/negative) |
| sentiment_score | FLOAT | não | - | - | Score (-1 a 1) |
| entities | JSONB | não | - | - | Entidades extraídas |
| consensus_log | JSONB | não | - | - | Log do grafo de consenso |
| pop_checklist | JSONB | não | - | - | Checklist de POPs |
| anomaly_detected | BOOLEAN | não | - | false | Anomalia detectada |
| summary | TEXT | não | - | - | Resumo da chamada |
| raw_insight | JSONB | não | - | - | Insight bruto do LLM |
| created_at | TIMESTAMPTZ | não | - | now() | Data de criação |

#### stt_metrics
| Campo | Tipo | Obrigatório | PK/FK | Default | Descrição |
|-------|------|-------------|-------|---------|-----------|
| id | UUID | sim | PK | uuid4 | ID interno |
| call_id | VARCHAR(128) | não | IDX | - | ID da chamada |
| provider | VARCHAR(32) | sim | - | - | deepgram/whisper |
| latency_ms | FLOAT | sim | - | - | Latência em ms |
| chunk_duration_ms | FLOAT | não | - | - | Duração do chunk |
| success | BOOLEAN | não | - | true | Se foi bem-sucedido |
| fallback_activated | BOOLEAN | não | - | false | Fallback ativado |
| error | TEXT | não | - | - | Mensagem de erro |
| created_at | TIMESTAMPTZ | não | - | now() | Data de criação |

## 2. Redis

### Chaves

| Chave | Tipo | TTL | Descrição |
|-------|------|-----|-----------|
| zenith:sip:ip_to_extension:{ip} | string | 3600s | IP → ramal SIP |
| zenith:sip:extension_to_ip:{ext} | string | 3600s | Ramal → IP |
| zenith:sip:extension_to_pbx:{ext} | string | - | Ramal → PBX ID |
| zenith:ws:agent_session:{uuid} | hash | 30-120s | Sessão WebSocket |
| pops:{tenant_id} | string (json) | 3600s | POPs do tenant |
| transcripts:batch:{call_id} | list | - | Buffer de transcrições |

### Streams

| Stream | Grupo Consumidor | Descrição |
|--------|-----------------|-----------|
| call:events | zenith-workers | Eventos de chamada em tempo real |
| call:post | - | Eventos pós-chamada |

## 3. Constantes e Enums

### CallDirection (Python enum)
``inbound`` | ``outbound``

### CallStatus (Python enum)
``ringing`` | ``in_progress`` | ``completed`` | ``failed``

### Config (Settings via pydantic-settings)

| Variável | Tipo | Default | Descrição |
|----------|------|---------|-----------|
| INSTANCE_ID | int | 1 | ID da instância |
| DEBUG | bool | false | Modo debug |
| LOG_LEVEL | str | "INFO" | Nível de log |
| REDIS_URL | str | "redis://redis:6379/0" | URL do Redis |
| DATABASE_URL | str | "postgresql+asyncpg://zenith:zenith@postgres:5432/zenith" | URL do DB |
| FREESWITCH_ESL_HOST | str | "172.20.0.1" | Host FreeSWITCH |
| FREESWITCH_ESL_PORT | int | 8021 | Porta ESL |
| FREESWITCH_ESL_PASSWORD | str | "ClueCon" | Senha ESL |
| DEEPGRAM_API_KEY | str | "" | API Key Deepgram |
| OLLAMA_URL | str | "http://ollama:11434" | URL Ollama |
| PIPER_TTS_URL | str | "http://piper-tts:5000" | URL Piper TTS |
| JWT_SECRET | str | "change-me-in-production" | Segredo JWT |
| JWT_ALGORITHM | str | "HS256" | Algoritmo JWT |
| JWT_EXPIRATION_MINUTES | int | 60 | Expiração JWT |
| REDIS_STREAM_CALL_EVENTS | str | "call:events" | Stream de eventos |
| REDIS_STREAM_POST_CALL | str | "call:post" | Stream pós-chamada |
| REDIS_CONSUMER_GROUP | str | "zenith-workers" | Grupo consumidor |
| STT_FALLBACK_TIMEOUT_MS | int | 500 | Timeout fallback STT |
| BATCH_INSERT_INTERVAL_SECONDS | int | 5 | Intervalo batch |
| AUDIO_RETENTION_DAYS | int | 90 | Retenção de áudio |
| S3_ENDPOINT | str | "" | Endpoint S3 |
| S3_ACCESS_KEY | str | "" | Access Key S3 |
| S3_SECRET_KEY | str | "" | Secret Key S3 |
| S3_BUCKET_PREFIX | str | "zenith-audio" | Prefixo bucket S3 |

## 4. Payloads e DTOs

### JWT Payload
```json
{
  "sub": "user@example.com",
  "tenant_id": "uuid",
  "role": "agent | tenant_admin",
  "exp": 1234567890,
  "iat": 1234567890
}
```

### PBXCreate (POST /api/v1/admin/pbxs)
| Campo | Tipo | Obrigatório | Validação |
|-------|------|-------------|-----------|
| name | str | sim | max_length=128 |
| host | str | sim | max_length=128 |
| port | int | não (default 5060) | ge=1, le=65535 |
