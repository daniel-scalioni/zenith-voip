# Módulo: database

> Gerado pelo Archaeologist — 2026-06-19
> **Re-extração incremental — 2026-07-27** (base `48da5b1` → `0658157`, delta D-06)
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/database/database.py` | Engine, sessions, multitenancy | 59 |
| `src/database/models.py` | ORM: Tenant, PBX, Call, Transcript, CallInsight, STTMetric | 125 |

## Fluxo de Controle

- `init_db()` → cria tabelas do schema public (Tenant, PBX)
- `create_tenant_schema(schema_name)` → cria schema e tabelas tenant-scoped
- `run_migrations_for_schema(schema_name)` → executa Alembic para schema específico
- `get_db()` → session scoped para public schema
- `get_tenant_db(tenant_schema)` → session com `search_path` setado.
  🆕 **Faz `await conn.commit()` explícito** ao final do `yield`. `session.commit()` só
  encerra a transação lógica do ORM; a `Connection` aberta por `engine.connect()`
  (com autobegin disparado pelo `SET search_path`) precisa de commit próprio — sem ele,
  sair do `async with` fazia **rollback silencioso** de tudo que o tenant gravou.
  Este era o bug que impedia a linha `Call` de persistir.

## Correções de tipagem ORM (🆕 2026-07)

Quatro colunas eram declaradas como `Column(default=...)` **sem tipo**, o que o SQLAlchemy 2.0
não aceita como coluna válida:

| Modelo | Coluna | Antes | Agora |
|---|---|---|---|
| `Transcript` | `is_final` | `Column(default=True)` | `Column(Boolean, default=True)` |
| `CallInsight` | `anomaly_detected` | `Column(default=False)` | `Column(Boolean, default=False)` |
| `STTMetric` | `success` | `Column(default=True)` | `Column(Boolean, default=True)` |
| `STTMetric` | `fallback_activated` | `Column(default=False)` | `Column(Boolean, default=False)` |

Além disso, o atributo `metadata` de `Call` e `Transcript` colidia com
`DeclarativeBase.metadata` do SQLAlchemy. Foi renomeado para **`extra_metadata`**, mapeado
explicitamente para a coluna física `metadata`:
`extra_metadata = Column("metadata", JSONB, nullable=True)`.
**O nome da coluna no banco não mudou** — apenas o atributo Python.

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
| duration_seconds | Float | não | - (calculado no hangup por `services/calls.py`) |
| metadata | JSONB | não | - (atributo Python: `extra_metadata`) |
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
| metadata | JSONB | não | - (atributo Python: `extra_metadata`) |
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
| 🆕 Escrita em schema de tenant exige commit explícito na Connection | `database.py:24-29` | 🟢 |
| 🆕 Nome do schema segue `tenant_<tenant_id>` | `services/calls.py:7-8` | 🟢 |

## Migrations

| Arquivo | Escopo |
|---|---|
| `alembic/versions/002_tenants_pbxs.py` | Schema public: `tenants`, `pbxs` |
| `alembic/versions/003_tenant_schema_tables.py` | Tabelas tenant-scoped |

Provisionamento de tenant é feito por `scripts/provision_tenant.py` 🆕 (cria tenant, schema
e PBX). O tenant real em produção é **Akom** (`tenant_id=akom`,
`pbx_id=c5bf3191-75b4-4a45-b5e1-c9b7942f8176`), com os mesmos valores replicados em
`freeswitch/conf/vars.xml` — 🟡 **duplicação de fonte de verdade**: se o `pbx_id` mudar no
banco e não no `vars.xml`, as chamadas passam a gravar com `pbx_id` inválido silenciosamente.
