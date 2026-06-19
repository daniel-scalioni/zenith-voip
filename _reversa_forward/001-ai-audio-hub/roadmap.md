# Roadmap: AI Hub for Audio (Zenith VoIP)

> Identificador: `001-ai-audio-hub`
> Data: `2026-05-17`
> Requirements: `_reversa_forward/001-ai-audio-hub/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

A abordagem técnica será a construção de um Hub Intermediário (SBC/B2BUA) baseado em FreeSWITCH para atuar como proxy transparente (SIP) entre os Telefones IP e o PBX legado. O FreeSWITCH fará o fork do áudio RTP via `mod_audio_fork` em WebSocket direto para o backend (sem intermediários), convertendo G.711 para PCM Linear 16kHz internamente. O backend orquestrador em Python (FastAPI) aplicará a arquitetura de microserviços com os padrões Strategy (STT/TTS/LLM intercambiáveis com fallback automático), Observer (dispatch via Redis Streams + WebSockets), Repository (PostgreSQL + JSONB) e Factory (pipelines por tenant). O barramento de eventos será unificado via Redis Streams com Consumer Groups e ACK, eliminando a necessidade de brokers externos. O orquestrador de IA (LangGraph) usará checkpointing via RedisSaver para resiliência a crashes, rodando em 2 instâncias FastAPI com sharding por `hash(call_id)` atrás do BunkerWeb WAF. Dados sensíveis (CPF, RG) serão processados exclusivamente por LLM self-hosted (Mistral 7B via Ollama) para compliance LGPD. O STT primário (Deepgram) terá fallback local automático (Whisper.cpp). O projeto será entregue em Fases (MVP1 Pós-chamada e MVP2 Tempo Real).

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| I. Orientação a Microserviços | Hub isolado em containers Docker, separando Telefonia, Orquestração IA, TTS, Observabilidade. | respeita |
| II. POO e Design Patterns | Strategy (STT/TTS/LLM com fallback), Observer (Redis Streams + WebSockets), Repository (DB), Factory (pipelines). | respeita |
| III. Baixo Acoplamento | O PBX legado não sofre modificação de código, apenas configuração SIP. TTS Local como microserviço HTTP isolado. | respeita |
| IV. Segurança First (Fail-Safe) | Ações críticas exigem consenso multi-agente. Bypass humano obrigatório. TLS/SRTP/JWT. LGPD. | respeita |
| V. Resiliência | Checkpointing LangGraph via Redis. Multi-instância FastAPI. Fallback STT local. Fallback WAV para TTS. | respeita |
| VI. Observabilidade | OpenTelemetry + Prometheus + Grafana. Health checks `/health` e `/ready`. | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | FreeSWITCH como B2BUA com mod_audio_fork via WebSocket | Melhor suporte nativo a manipulação e extração de áudio em tempo real. WS garante entrega ordenada. | Kamailio (complexo para RTP), Asterisk (pesado), UDP raw (perda de chunks). | 🟢 |
| D-02 | Python FastAPI (2 instâncias + BunkerWeb WAF) | Suporte async perfeito. Multi-instância com sharding por call_id mitiga SPOF. | Node.js, Go, instância única. | 🟢 |
| D-03 | PostgreSQL com JSONB + Batch Insert para transcripts | Integridade relacional + flexibilidade NoSQL. Transcripts acumulados em Redis List e persistidos em lote no fim da chamada para evitar gargalo de I/O. | MongoDB puro, MySQL, inserts individuais. | 🟢 |
| D-04 | Deepgram STT (primário) + Whisper.cpp (fallback local) | Deepgram: latência líder (<300ms). Whisper.cpp: fallback automático se internet cair (Strategy Pattern). | Deepgram sem fallback (SPOF inaceitável). | 🟢 |
| D-05 | Redis Streams (Event Bus unificado) | Persistência com ACK + Consumer Groups. Um broker só para RT e pós-chamada. Elimina RabbitMQ. | Redis Pub/Sub (fire-and-forget), RabbitMQ (peso extra), Kafka (overengineering). | 🟢 |
| D-06 | LangGraph com RedisSaver (Checkpointing) | Estado do orquestrador persistido a cada transição. Em crash, recupera pelo call_id. | LangGraph sem checkpointing (perda total em crash). | 🟢 |
| D-07 | Pipeline Multi-Agente (escopo: ações físicas) | Consenso (Extrator→Revisor→Decisor) apenas para ações críticas. Extração RT usa saída direta sem consenso. | Consenso para tudo (latência inaceitável no Agent Assist). | 🟢 |
| D-08 | Extração Triage Mista (Regex + LLM local) | Regex filtra ~90% dos chunks; LLM local (Mistral 7B) só para validação de suspeitas. Senhas via DTMF. | Regex puro (falha com hesitação), LLM para tudo (custo/latência alto). | 🟢 |
| D-09 | TTS Local (Piper/Coqui) + Fallback WAV | Piper em CPU, Coqui com GPU. Se TTS travar, WAV pré-gravados via ESL playback. | TTS em nuvem (latência), sem fallback (mudo em crash). | 🟢 |
| D-10 | LLM Self-hosted (Mistral 7B / Ollama) para LGPD | CPF/RG processados localmente. Nenhum dado sensível sai da infra. | GPT-4o-mini via API (violação LGPD). | 🟢 |
| D-11 | Speaker Diarization por canal + Deepgram | mod_audio_fork envia TX/RX em canais separados. Deepgram com `diarize:true` como backup. | Transcrição sem diarização (sopa de vozes inútil). | 🟢 |
| D-12 | Arq como Worker Assíncrono | Asyncio-nativo, integra naturalmente com Redis Streams. Mais leve que Celery. | Celery (pesado, não-asyncio). | 🟢 |
| D-13 | OpenTelemetry + Prometheus + Grafana | Tracing distribuído, métricas de latência STT/LLM, alertas de degradação. | Sem observabilidade (inaceitável para mission-critical). | 🟢 |
| D-14 | TLS/SRTP + JWT + BunkerWeb WAF | SIP criptografado, API autenticada, WAF já em uso pelo cliente. | Stack sem criptografia (inaceitável). | 🟢 |
| D-15 | Tauri (Desktop Widget Overlay) | ~15MB RAM (WebView2 nativo Windows), always-on-top, system tray. Operador já tem tela lotada. | Electron (~200MB RAM), Browser tab (sem espaço), PyQt (pesado). | 🟢 |

## 4. Premissas

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------| 
| O PBX legado aceita registros de peers tipo Trunk ou SBC. | Seção 2 (Contexto) | Inviabiliza arquitetura proxy transparente. |
| O servidor local possui recursos (CPU) para rodar TTS + Whisper.cpp + Ollama (Mistral 7B). | Sessão de Brainstorming | Latência inaceitável. LLM local exige ~8GB RAM + CPU razoável. |
| BunkerWeb WAF já está operacional e aceita configuração de sticky sessions por header. | Decisão do Usuário (3A) | Necessário para sharding por call_id. |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| FreeSWITCH SBC/Media Server | `n/a` (Greenfield) | componente-novo | B2BUA transparente + mod_audio_fork (WS) + ESL para injeção de áudio (Whisper/Filler). |
| AI Hub API (FastAPI x2) | `n/a` (Greenfield) | componente-novo | Orquestrador: ingestor de áudio, ESL client, WebSockets, Redis Streams publisher, LangGraph runner. |
| Worker Analytics (Arq) | `n/a` (Greenfield) | componente-novo | Processamento assíncrono pós-chamada (sentimento, auditoria) via Redis Streams consumer. |
| Agent Assist Frontend | `n/a` (Greenfield) | componente-novo | Painel do atendente recebendo eventos via WebSocket (transcrição, entidades, alertas). |
| Local TTS Service | `n/a` (Greenfield) | componente-novo | Microserviço HTTP renderizador de texto para áudio (Piper TTS). Fallback WAV. |
| Local LLM Service (Ollama) | `n/a` (Greenfield) | componente-novo | Mistral 7B self-hosted para extração de entidades sensíveis (LGPD). |
| STT Fallback (Whisper.cpp) | `n/a` (Greenfield) | componente-novo | Motor STT local ativado automaticamente se Deepgram falhar. |
| Observabilidade Stack | `n/a` (Greenfield) | componente-novo | OpenTelemetry Collector + Prometheus + Grafana + Loki. |
| Desktop Widget (Tauri) | `n/a` (Greenfield) | componente-novo | Overlay always-on-top: checklist POP + barra de controle + status STT. System tray no Windows. |

## 6. Delta no modelo de dados

- Resumo: Criação das tabelas `calls`, `transcripts`, e `call_insights` (JSONB para logs dinâmicos de IA e debate multi-agente).
- Transcripts usam batch insert (acumulados em Redis List durante chamada, persistidos em lote ao final).
- Detalhe completo em: `_reversa_forward/001-ai-audio-hub/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------| 
| AI Webhook (Pós-chamada) | Webhook HTTP | `_reversa_forward/001-ai-audio-hub/interfaces/ai-webhook.md` |
| Agent Assist (Tempo Real) | WebSocket | `_reversa_forward/001-ai-audio-hub/interfaces/agent-websocket.md` |

## 8. Plano de migração

### Fase 1 — Fundação e Captura (MVP1: Pós-Chamada)
1. Configuração do ambiente Docker (FreeSWITCH, PostgreSQL, Redis, FastAPI x2, BunkerWeb WAF, Prometheus, Grafana).
2. Provisionamento do FreeSWITCH como SIP Proxy Transparente e teste de bypass com o PBX.
3. Ativação do `mod_audio_fork` com envio via WebSocket para o backend.
4. Implementação de Speaker Diarization por canal no ingestor.
5. STT offline (Deepgram batch) + Whisper.cpp fallback + Arq worker para auditoria e sentimento pós-chamada.
6. Dispatcher de Webhook pós-chamada via Redis Streams.

### Fase 2 — Tempo Real e Agent Assist (MVP2)
1. STT streaming (Deepgram RT + fallback Whisper.cpp) com transcrição ao vivo.
2. Extração de Entidades Triage (Regex/spaCy Camada 1 + Mistral/Ollama Camada 2).
3. WebSocket Server para Agent Assist (Live Transcript + Entidades + Alertas).
4. Frontend do painel do atendente.

### Fase 3 — Participação Ativa e Consenso
1. FreeSWITCH Conference Bridge / Eavesdrop para injeção seletiva de áudio.
2. Whisper Mode (uuid_play no agent_uuid) + Filler Audio (uuid_play no customer_uuid).
3. TTS Local (Piper + fallback WAV pré-gravados).
4. LangGraph Multi-Agente (Extrator → Revisor → Decisor) com checkpointing Redis.
5. Desktop Widget Tauri (checklist POP + barra de controle + status).
6. Alertas passivos de Fúria no widget.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Deepgram indisponível (internet cai) | alto | médio | Fallback automático Whisper.cpp local via Strategy Pattern. Monitoramento contínuo de latência. |
| Crash do container FastAPI (perda de estado IA) | alto | médio | Checkpointing LangGraph via RedisSaver. 2 instâncias (crash afeta 50%, não 100%). |
| Vazamento de áudio no Whisper Mode (morador ouve o sussurro) | alto | médio | Validação obrigatória via teste gravado bilateral. Mapeamento explícito de UUIDs por perna. |
| PBX legado rejeitar tráfego de proxy SIP | alto | baixo | PoC de sinalização SIP na primeira sprint para ajustar cabeçalhos (Record-Route, etc). |
| Gargalo de I/O no PostgreSQL com transcripts RT | médio | médio | Batch insert via Redis List. Considerar TimescaleDB se >50 chamadas simultâneas. |
| Falso positivo do Multi-Agente parando operações lícitas | alto | médio | Bypass manual (Human Fallback) no painel do operador. Consenso apenas para ações físicas. |
| Latência do consenso multi-agente (3-5s) | médio | alto | Fan-out paralelo no LangGraph. SLM local para Revisor. Cache de POPs em Redis. Filler Audio. |
| TTS local trava (Piper/Coqui crash) | médio | baixo | Fallback WAV pré-gravados + supervisord auto-restart. Health check `/health`. |
| LLM local (Ollama) lento sem GPU | médio | médio | Usar modelo quantizado (Q4/Q5). Ollama com `num_gpu=0` em CPU é viável para Mistral 7B. |
| Violação LGPD (dados sensíveis na nuvem) | alto | baixo | LLM local obrigatório. Senhas via DTMF. Zero persistência de senhas. |

## 10. Critério de pronto
- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `cross-check.md` (se executado) sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado
- [ ] Teste gravado bilateral confirmando isolamento do Whisper Mode
- [ ] Dashboard Grafana operacional com métricas STT/LLM
- [ ] Teste de caos: restart do container FastAPI durante chamada ativa com recuperação de estado

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-05-16 | Versão inicial gerada por `/reversa-plan`. | reversa |
| 2026-05-16 | Refatoração profunda para englobar arquitetura Ativa (Whisper, TTS Local, Multi-Agent). | reversa |
| 2026-05-17 | Revisão geral: Peer Review de 3 LLMs. IDs deduplicados. Decisões D-01 a D-14 consolidadas. Redis Streams, Fallback STT, LGPD, Observabilidade, Multi-instância, Segurança TLS, Arq worker. | reversa |