# Módulo: database

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/database/database.py` | Engine, sessions, multitenancy | 54 |
| `src/database/models.py` | ORM: Tenant, PBX, Call, Transcript, CallInsight, STTMetric | 125 |

## Fluxo de Controle

- `init_db()` → cria tabelas do schema public (Tenant, PBX)
- `create_tenant_schema(schema_name)` → cria schema e tabelas tenant-scoped
- `run_migrations_for_schema(schema_name)` → executa Alembic para schema específico
- `get_db()` → session scoped para public schema
- `get_tenant_db(tenant_schema)` → session com search_path setado

## Modelos de Dados

### Tenant (public)
| Campo | Tipo | Obrigatório | Default |
|-------|------|-------------|---------|
| id | UUID | sim | uuid4 |
| name | String(128) | sim | - |
| schema_name | String(64) | sim (unique) | - |
| status | String(32) | não | "active" |
| created_at | DateTime | não | now() |
| updated_at | DateTime | não | now() |
| *pbxs* | relationship | - | cascade delete |

### PBX (public)
| Campo | Tipo | Obrigatório | Default |
|-------|------|-------------|---------|
| id | UUID | sim | uuid4 |
| tenant_id | UUID FK | sim | - |
| name | String(128) | sim | - |
| host | String(128) | sim | - |
| port | Integer | não | 5060 |
| created_at | DateTime | não | now() |
| updated_at | DateTime | não | now() |

### Call (tenant schema)
| Campo | Tipo | Obrigatório | Default |
|-------|------|-------------|---------|
| id | UUID | sim | uuid4 |
| call_id | String(128) | sim (unique, index) | - |
| agent_uuid | String(128) | não | - |
| customer_uuid | String(128) | não | - |
| pbx_id | UUID | não | - |
| agent_sip_extension | String(64) | não | - |
| direction | CallDirection enum | sim | - |
| status | CallStatus enum | não | in_progress |
| caller_number | String(32) | não | - |
| callee_number | String(32) | não | - |
| started_at | DateTime | não | now() |
| ended_at | DateTime | não | - |
| duration_seconds | Float | não | - |
| metadata | JSONB | não | - |
| *transcripts* | relationship | - | cascade delete |
| *insights* | relationship | - | cascade delete |

### Transcript (tenant schema)
| Campo | Tipo | Obrigatório | Default |
|-------|------|-------------|---------|
| id | UUID | sim | uuid4 |
| call_id | UUID FK | sim | - |
| channel | String(16) | sim | - |
| speaker | String(64) | não | - |
| text | Text | sim | - |
| confidence | Float | não | - |
| start_time | Float | sim | - |
| end_time | Float | sim | - |
| is_final | Boolean | não | true |
| metadata | JSONB | não | - |
| created_at | DateTime | não | now() |

### CallInsight (tenant schema)
| Campo | Tipo | Obrigatório | Default |
|-------|------|-------------|---------|
| id | UUID | sim | uuid4 |
| call_id | UUID FK | sim | - |
| sentiment | String(32) | não | - |
| sentiment_score | Float | não | - |
| entities | JSONB | não | - |
| consensus_log | JSONB | não | - |
| pop_checklist | JSONB | não | - |
| anomaly_detected | Boolean | não | false |
| summary | Text | não | - |
| raw_insight | JSONB | não | - |
| created_at | DateTime | não | now() |

### STTMetric (tenant schema)
| Campo | Tipo | Obrigatório | Default |
|-------|------|-------------|---------|
| id | UUID | sim | uuid4 |
| call_id | String(128) | não | - |
| provider | String(32) | sim | - |
| latency_ms | Float | sim | - |
| chunk_duration_ms | Float | não | - |
| success | Boolean | não | true |
| fallback_activated | Boolean | não | false |
| error | Text | não | - |
| created_at | DateTime | não | now() |

## Enums

### CallDirection
| Valor | Descrição |
|-------|-----------|
| inbound | Chamada recebida |
| outbound | Chamada realizada |

### CallStatus
| Valor | Descrição |
|-------|-----------|
| ringing | Chamando |
| in_progress | Em andamento |
| completed | Finalizada |
| failed | Falhou |

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Multitenancy com schema isolado por tenant | `database.py:33-37` | 🟢 |
| PBX pertence a um tenant (FK cascade) | `models.py:44` | 🟢 |
| Transcripts e insights em cascade com Call | `models.py:74-75` | 🟢 |
| Migrations executadas por schema | `database.py:40-47` | 🟢 |
