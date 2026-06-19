# Análise de Código — zenith-voip

> Gerado pelo Archaeologist — 2026-06-19
> Nível de documentação: completo
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Sumário

**Zenith AI Audio Hub** v1.0.0 é um sistema de IA para transcrição e análise de chamadas VoIP em tempo real. Escrito em Python (FastAPI), integra-se ao FreeSWITCH via ESL, usa Deepgram + Whisper.cpp para STT com fallback automático, Ollama (Mistral 7B) para LLM local, Piper TTS para síntese de voz, e PostgreSQL com multitenancy físico.

## Arquitetura Geral

```
[FreeSWITCH] ←ESL→ [FastAPI (2 instâncias)] ←HTTP/WS→ [Widget Tauri]
                       ↓
              [Redis Streams] ←→ [Workers ARQ]
                       ↓
              [PostgreSQL multitenant]
```

### Fluxo Principal de uma Chamada

1. **FreeSWITCH** recebe chamada SIP e gera eventos ESL
2. **ESLClient** escuta eventos: CHANNEL_CREATE → CHANNEL_ANSWER → CHANNEL_HANGUP
3. **AudioIngestor** recebe stream de áudio via WebSocket do FreeSWITCH
4. **Chunks de áudio** publicados no Redis Stream (call:events)
5. **Workers ARQ** consomem: STT (Deepgram → fallback Whisper), extração de dados, anomalias
6. **Transcripts** bufferizados no Redis e persistidos em lote no PostgreSQL
7. **ConsensusGraph** (LangGraph) valida entidades em 3 ciclos
8. **Resultados** enviados via WebSocket para o Widget Tauri do operador
9. **Pós-chamada**: análise de sentimento, auditoria, webhooks
10. **Cleanup diário** (03:00): deleta áudio S3 com mais de 90 dias

## Módulos Analisados (12)

### 1. api — Interface REST + WebSocket
- FastAPI com lifespan (init_db)
- JWT auth com RBAC (agent / tenant_admin)
- Rate limit in-memory (100 req/60s por IP)
- CRUD de PBXs (/api/v1/admin/pbxs)
- WebSocket Agent Assist com auto-link SIP
- Webhook dispatcher pós-chamada
- **🟢 5 arquivos, 307 linhas**

### 2. ai — Inteligência Artificial
- Detecção de anomalias de tom (27 keywords de fúria + padrões de estresse)
- Grafo de consenso LangGraph: extractor → reviewer → decider (até 3 iterações)
- Cache Redis de POPs (TTL 1h)
- **🟢 3 arquivos, 191 linhas**

### 3. audio — Ingestão de Áudio
- Recebe streams forked do FreeSWITCH via WebSocket
- Bufferiza chunks em memória
- Publica eventos no Redis Stream com metadados da chamada
- **🟢 1 arquivo, 74 linhas**

### 4. database — Persistência
- Multitenancy físico: schemas PostgreSQL isolados por tenant
- 6 modelos ORM: Tenant, PBX, Call, Transcript, CallInsight, STTMetric
- Migrations via Alembic (3 revisões)
- Tenant scoped sessions com search_path
- **🟢 2 arquivos, 179 linhas**

### 5. events — Event Bus
- Abstração Redis Streams: publish, consume, ack, create_group
- 2 streams: call:events (tempo real), call:post (pós-chamada)
- Consumer group: zenith-workers
- **🟢 1 arquivo, 38 linhas**

### 6. extraction — Extração de Dados
- 6 padrões regex (CPF, RG, telefone, placa, CEP, cartão de crédito)
- Cartão de crédito marcado como sensitive (sanitização via LLM)
- LLM local (Ollama Mistral 7B) para correção contextual
- **🟢 2 arquivos, 67 linhas**

### 7. observability — Telemetria
- OpenTelemetry + FastAPI instrumentation
- 16 métricas Prometheus (STT, LLM, chamadas, S3, Redis, DB)
- Endpoint /metrics
- **🟢 2 arquivos, 192 linhas**

### 8. services — Serviços de IA
- Strategy Pattern: STTStrategy, TTSStrategy, LLMStrategy
- AutoFallback STT: Deepgram → Whisper.cpp (timeout 500ms, confidence > 0.3)
- Piper TTS com fallback WAV local
- Repository genérico CRUD
- **🟢 6 arquivos, 245 linhas**

### 9. telephony — Integração FreeSWITCH
- Cliente ESL completo com reconexão automática
- Mapeamento SIP/IP no Redis (TTL 1h)
- Detecção de *88 para manual linkage
- Whisper Mode: TTS no canal do agente
- Filler audio em chamadas
- **🟢 3 arquivos, 250 linhas**

### 10. workers — Background Jobs
- ARQ workers: cleanup S3 (cron 03:00), upload áudio, pós-chamada, transcript persist
- Retenção de 90 dias, delete em lotes de 1000
- Buffer de transcrições no Redis com flush batch
- **🟢 4 arquivos, 244 linhas**

### 11. widget — Desktop Widget
- Tauri (Rust) sempre-on-top, 320x500, transparente
- Status: standby/connected/disconnected/fallback
- Checklist de POPs, transcrição, alertas, copiloto
- System tray com Mostrar/Sair
- **🟢 4 arquivos**

### 12. infra — Infraestrutura
- 14 containers Docker (2 FastAPI, FreeSWITCH, Redis, PostgreSQL, Ollama, Piper, BunkerWeb, Prometheus, Grafana, Loki)
- Sticky session via BunkerWeb (X-Call-ID)
- GPU reservada para Ollama
- Deploy manual com controle de revisões
- **🟢 10+ arquivos de configuração**

## Algoritmos-Chave

| Algoritmo | Módulo | Descrição |
|-----------|--------|-----------|
| AutoFallback STT | services | Deepgram com timeout 500ms → Whisper.cpp |
| SIP Auto-Link | api | IP do WS → Redis → ramal SIP |
| Consensus Graph | ai | LangGraph 3 nós, até 3 iterações |
| Anomaly Detection | ai | Keywords + padrões estresse, threshold 3 |
| Fúria Score | ai | 13 keywords em PT-BR |
| Multitenancy | database | Schema PostgreSQL por tenant |
| ESL Reconexão | telephony | Auto-reconnect com backoff 2s |
| S3 Cleanup | workers | Lotes de 1000, retenção 90 dias |

## Totalização

| Métrica | Valor |
|---------|-------|
| Arquivos de código | 32 (src) |
| Arquivos de teste | 7 |
| Total linhas de código | ~1.800 |
| Dependências | 31 pacotes Python |
| Containers Docker | 14 |
| Tabelas no banco | 6 |
| Módulos | 12 |
