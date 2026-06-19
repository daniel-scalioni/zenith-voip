# ERD Completo — zenith-voip

> Gerado pelo Architect — 2026-06-19
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Propósito

Diagrama completo de entidades e relacionamentos do banco de dados PostgreSQL.

## Diagrama ERD (Mermaid)

```mermaid
erDiagram
  Tenant ||--o{ PBX : "possui"
  Tenant ||--|| "Schema tenant_{id}" : "isola"

  PBX {
    uuid id PK
    uuid tenant_id FK
    varchar name
    varchar host
    int port "default 5060"
    timestamptz created_at
    timestamptz updated_at
  }

  Tenant {
    uuid id PK
    varchar name
    varchar schema_name UQ
    varchar status "active/inactive"
    timestamptz created_at
    timestamptz updated_at
  }

  Call {
    uuid id PK
    varchar call_id UK
    varchar agent_uuid "FreeSWITCH UUID"
    varchar customer_uuid FK
    uuid pbx_id FK
    varchar agent_sip_extension
    varchar direction "inbound|outbound"
    varchar status "ringing|in_progress|completed|failed"
    varchar caller_number
    varchar callee_number
    timestamptz started_at
    timestamptz ended_at
    float duration_seconds
    jsonb metadata
    timestamptz created_at
    timestamptz updated_at
  }

  Transcript {
    uuid id PK
    uuid call_id FK
    varchar channel "tx|rx"
    varchar speaker
    text text
    float confidence
    float start_time
    float end_time
    boolean is_final
    jsonb metadata
    timestamptz created_at
  }

  CallInsight {
    uuid id PK
    uuid call_id FK
    varchar sentiment "positive|neutral|negative"
    float sentiment_score "-1 a 1"
    jsonb entities "entidades extraídas"
    jsonb consensus_log "log do LangGraph"
    jsonb pop_checklist
    boolean anomaly_detected
    text summary
    jsonb raw_insight
    timestamptz created_at
  }

  STTMetric {
    uuid id PK
    varchar call_id
    varchar provider "deepgram|whisper"
    float latency_ms
    float chunk_duration_ms
    boolean success
    boolean fallback_activated
    text error
    timestamptz created_at
  }

  Call ||--o{ Transcript : "possui"
  Call ||--o| CallInsight : "possui"
  Call }o--|| PBX : "pertence"
```

## Esquemas do Banco

### Schema `public`

Tabelas globais, visíveis a todos os tenants.

| Tabela | Descrição | Confiança |
|--------|-----------|-----------|
| **tenants** | Cadastro de inquilinos (clientes) | 🟢 |
| **pbxs** | Centrais telefônicas vinculadas a tenants | 🟢 |

### Schema `tenant_{id}` (um por tenant)

Tabelas criadas dinamicamente por tenant.

| Tabela | Descrição | Linhas estimadas | Confiança |
|--------|-----------|-----------------|-----------|
| **calls** | Chamadas telefônicas | Alta (milhares/dia) | 🟢 |
| **transcripts** | Segmentos de transcrição | Muito alta (N por call) | 🟢 |
| **call_insights** | Análise pós-chamada | 1 por call | 🟢 |
| **stt_metrics** | Métricas de STT por requisição | Alta (N por call) | 🟢 |

## Detalhamento de Entidades

### Tenant

| Campo | Tipo | Restrições | Descrição |
|-------|------|-----------|-----------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Identificador único |
| name | VARCHAR(128) | NOT NULL | Nome do inquilino |
| schema_name | VARCHAR(64) | NOT NULL, UNIQUE | Nome do schema PostgreSQL |
| status | VARCHAR(32) | DEFAULT 'active' | active / inactive |
| created_at | TIMESTAMPTZ | DEFAULT now() | Data de criação |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Data de atualização |

### PBX

| Campo | Tipo | Restrições | Descrição |
|-------|------|-----------|-----------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Identificador único |
| tenant_id | UUID | FK → tenants.id, ON DELETE CASCADE | Tenant proprietário |
| name | VARCHAR(128) | NOT NULL | Nome do PBX |
| host | VARCHAR(128) | NOT NULL | Host/IP do PBX |
| port | INTEGER | DEFAULT 5060 | Porta SIP |
| created_at | TIMESTAMPTZ | DEFAULT now() | Data de criação |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Data de atualização |

### Call

| Campo | Tipo | Restrições | Descrição |
|-------|------|-----------|-----------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Identificador interno |
| call_id | VARCHAR(128) | UNIQUE, INDEX | ID externo da chamada (FreeSWITCH) |
| agent_uuid | VARCHAR(128) | - | UUID do agente no FreeSWITCH |
| customer_uuid | VARCHAR(128) | - | UUID do cliente no FreeSWITCH |
| pbx_id | UUID | - | ID do PBX de origem |
| agent_sip_extension | VARCHAR(64) | - | Ramal SIP do agente |
| direction | VARCHAR(16) | NOT NULL | inbound / outbound |
| status | VARCHAR(32) | DEFAULT 'in_progress' | ringing / in_progress / completed / failed |
| caller_number | VARCHAR(32) | - | Número do chamador |
| callee_number | VARCHAR(32) | - | Número do destino |
| started_at | TIMESTAMPTZ | DEFAULT now() | Início da chamada |
| ended_at | TIMESTAMPTZ | - | Término da chamada |
| duration_seconds | FLOAT | - | Duração em segundos |
| metadata | JSONB | - | Metadados extras |
| created_at | TIMESTAMPTZ | DEFAULT now() | Data de criação |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Data de atualização |

### Transcript

| Campo | Tipo | Restrições | Descrição |
|-------|------|-----------|-----------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Identificador interno |
| call_id | UUID | FK → calls.id, ON DELETE CASCADE | Chamada relacionada |
| channel | VARCHAR(16) | NOT NULL | tx (agente) / rx (cliente) |
| speaker | VARCHAR(64) | - | Identificador do falante |
| text | TEXT | NOT NULL | Texto transcrito |
| confidence | FLOAT | - | Confiança da transcrição (0-1) |
| start_time | FLOAT | NOT NULL | Início do segmento (segundos) |
| end_time | FLOAT | NOT NULL | Fim do segmento (segundos) |
| is_final | BOOLEAN | DEFAULT true | Se é transcrição final |
| metadata | JSONB | - | Metadados extras |
| created_at | TIMESTAMPTZ | DEFAULT now() | Data de criação |

### CallInsight

| Campo | Tipo | Restrições | Descrição |
|-------|------|-----------|-----------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Identificador interno |
| call_id | UUID | FK → calls.id, ON DELETE CASCADE | Chamada relacionada |
| sentiment | VARCHAR(32) | - | positive / neutral / negative |
| sentiment_score | FLOAT | - | Score de sentimento (-1 a 1) |
| entities | JSONB | - | Entidades extraídas (CPF, RG, etc.) |
| consensus_log | JSONB | - | Log do grafo de consenso LangGraph |
| pop_checklist | JSONB | - | Checklist de POPs cumpridos |
| anomaly_detected | BOOLEAN | DEFAULT false | Se anomalia foi detectada |
| summary | TEXT | - | Resumo da chamada |
| raw_insight | JSONB | - | Insight bruto do LLM |
| created_at | TIMESTAMPTZ | DEFAULT now() | Data de criação |

### STTMetric

| Campo | Tipo | Restrições | Descrição |
|-------|------|-----------|-----------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Identificador interno |
| call_id | VARCHAR(128) | INDEX | ID da chamada |
| provider | VARCHAR(32) | NOT NULL | deepgram / whisper |
| latency_ms | FLOAT | NOT NULL | Latência em milissegundos |
| chunk_duration_ms | FLOAT | - | Duração do chunk de áudio |
| success | BOOLEAN | DEFAULT true | Se a requisição foi bem-sucedida |
| fallback_activated | BOOLEAN | DEFAULT false | Se o fallback foi ativado |
| error | TEXT | - | Mensagem de erro (se houver) |
| created_at | TIMESTAMPTZ | DEFAULT now() | Data de criação |

## Relacionamentos

| De | Para | Tipo | Cardinalidade | Descrição |
|----|------|------|--------------|-----------|
| Tenant | PBX | FK | 1:N | Um tenant pode ter múltiplos PBXs |
| PBX | Call | FK | 1:N | Um PBX pode ter múltiplas chamadas |
| Call | Transcript | FK | 1:N | Uma chamada pode ter múltiplos segmentos de transcrição |
| Call | CallInsight | FK | 1:1 | Uma chamada tem um insight (pós-análise) |
| Call | STTMetric | FK | 1:N | Uma chamada pode ter múltiplas métricas de STT |

## Índices e Constraints

| Tabela | Índice/Constraint | Tipo | Coluna(s) |
|--------|------------------|------|-----------|
| tenants | tenants_pkey | PK | id |
| tenants | tenants_schema_name_key | UNIQUE | schema_name |
| pbxs | pbxs_pkey | PK | id |
| calls | calls_pkey | PK | id |
| calls | calls_call_id_key | UNIQUE | call_id |
| calls | idx_calls_call_id | INDEX | call_id |
| calls | idx_calls_status | INDEX | status |
| transcripts | transcripts_pkey | PK | id |
| transcripts | idx_transcripts_call_id | INDEX | call_id |
| call_insights | call_insights_pkey | PK | id |
| call_insights | idx_call_insights_call_id | INDEX | call_id |
| stt_metrics | stt_metrics_pkey | PK | id |
| stt_metrics | idx_stt_metrics_call_id | INDEX | call_id |

## Observações

- Todas as tabelas de dados dos tenants (calls, transcripts, call_insights, stt_metrics) residem em schemas isolados (`tenant_{id}`)
- A FK `calls.pbx_id` aponta para `public.pbxs.id` (tabela global)
- Transcripts usam ON DELETE CASCADE — deletar uma call remove todos os transcripts associados
- `call_insights` tem relação 1:1 com `calls` (uma call → um insight agregado)
