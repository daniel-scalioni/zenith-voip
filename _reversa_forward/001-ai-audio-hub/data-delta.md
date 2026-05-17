# Data Delta: AI Hub

> Atualizado: 2026-05-17 (Peer Review incorporado)

Nenhuma tabela de PBX legado será alterada. Criação de schema isolado (Microserviço AI Hub) gerenciado via Alembic (Migrations do FastAPI).

## Novas Tabelas

### `calls`
- `id`: UUID (PK)
- `sip_call_id`: VARCHAR (Original do PBX, mapeamento único)
- `caller_id`: VARCHAR
- `callee_id`: VARCHAR
- `start_time`: TIMESTAMP
- `end_time`: TIMESTAMP
- `status`: ENUM (ongoing, completed, error)
- `audio_url`: VARCHAR (Path do disco local para a gravação)
- `agent_uuid`: VARCHAR (UUID da perna FreeSWITCH do atendente)
- `customer_uuid`: VARCHAR (UUID da perna FreeSWITCH do morador)
- `tenant_id`: VARCHAR (Identificador do condomínio — necessário para RN-05 Consciência de Domínio)

### `transcripts`
- `id`: UUID (PK)
- `call_id`: UUID (FK)
- `speaker`: ENUM (agent, customer)  ← Speaker Diarization (RN-10)
- `start_time`: FLOAT (segundos desde o início)
- `end_time`: FLOAT (segundos)
- `text`: TEXT

**Estratégia de performance (HI-02):** Durante a chamada ativa, utterances são acumuladas numa Redis List (`transcript:{call_id}`). No fim da chamada, o worker Arq executa um batch INSERT único no PostgreSQL. Índices são criados APÓS a persistência para evitar gargalo de I/O durante o fluxo RT.

> Se o volume exceder 50 chamadas simultâneas, considerar a extensão TimescaleDB para particionamento por tempo.

### `call_insights` (Padrão Híbrido Relacional + JSONB)
- `id`: UUID (PK)
- `call_id`: UUID (FK)
- `sentiment`: VARCHAR (positive, neutral, negative)
- `audit_score`: INTEGER (0 a 100)
- `checklist_result`: JSONB (Itens do POP verificados: `{"item": "Pediu nome", "passed": true}`)
- `entities_extracted`: JSONB (Entidades extraídas: `{"cpf": "123.456.789-00", "placa": "ABC1D23"}`)
- `consensus_log`: JSONB (Log do debate multi-agente: `{"extractor": "autorizar", "reviewer": "negar", "reason": "coação detectada"}`)
- `raw_data`: JSONB (Dados brutos gerados pela IA, metadados flexíveis)
  - *Nota Arquitetural*: O uso de JSONB no PostgreSQL evita migrações constantes para cada nova entidade extraída pelo LLM.

### `stt_metrics` (Observabilidade — CR-04)
- `id`: SERIAL (PK)
- `timestamp`: TIMESTAMP
- `provider`: ENUM (deepgram, whisper_cpp)
- `latency_ms`: INTEGER
- `was_fallback`: BOOLEAN
- `call_id`: UUID (FK, nullable)

> Tabela append-only para alimentar dashboards Prometheus/Grafana com métricas de desempenho do STT.
