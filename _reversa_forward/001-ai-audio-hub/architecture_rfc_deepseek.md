Architecture RFC DeepSeek — Análise Crítica & Soluções
Documento de referência: architecture_rfc.md  
Autor da análise: DeepSeek (Arquitetura Sênior)  
Data: 2026-05-17  
Status: Crítica técnica vinculante — recomendações devem ser resolvidas antes da codificação.
Sumário Executivo
O RFC atual tem méritos (FreeSWITCH, LangGraph, TTS local), mas contém 5 problemas críticos, 7 problemas de alta severidade e várias lacunas que tornam a arquitetura frágil para um sistema mission-critical de portaria remota. Abaixo, cada ponto com solução concreta.
🔴 PROBLEMAS CRÍTICOS (Devem ser resolvidos antes do MVP1)
C-01: Deepgram como dependência obrigatória para STT em tempo real
Problema: O RFC coloca Deepgram (API externa via Internet) como o motor primário de STT em tempo real (RF-04). Se a internet da Akom cair ou a latência exceder 300ms, o sistema inteiro de Agent Assist cega. Para portaria remota, isso é inaceitável.
Solução — Fallback local obrigatório:
┌─────────────────────────────────────────┐
│  STT Strategy (Interface)               │
│  ├── DeepgramSTT (primário, nuvem)      │
│  ├── WhisperCppSTT (fallback local,     │
│  │   on-premises, CPU/GPU)              │
│  └── AutoFallback: deepgram timeout >   │
│      500ms → WhisperCpp local           │
└─────────────────────────────────────────┘
- 
Whisper.cpp roda em CPU com quantização (modelo small ou medium, Q5) com latência ~500ms em CPU moderna.
- 
Deepgram continua sendo o padrão para menor latência (<300ms), mas o fallback é automático e transparente.
- 
Implementação: Adicionar src/stt/whisper_cpp_stt.py + download do modelo em Dockerfile.
C-02: Perda de estado do LangGraph com restart do backend
Problema: Dilema 3, Opção B admite que restart do container de backend perde "a inteligência" de todas as ligações ativas. Em sistema mission-critical, uma chamada em andamento não pode perder seu contexto de IA.
Solução — State Store externo via Redis Streams:
- 
LangGraph suporta Checkpointer (persistência de estado). Configurar RedisSaver para salvar o estado do grafo a cada transição de nó.
- 
Em crash/restart, o grafo é recuperado pelo call_id e continua do último checkpoint.
- 
Código:
from langgraph.checkpoint.aiosqlite import SqliteSaver  # ou RedisSaver
graph = builder.compile(checkpointer=RedisSaver(redis_client))
- 
Custo adicional: ~50μs por checkpoint em Redis local (desprezível).
C-03: Ausência de observabilidade estruturada
Problema: Nenhum requisito de monitoramento para um sistema que decide abrir portas. Sem métricas de latência STT/LLM, sem tracing de decisões multi-agente, sem alerta de degradação.
Solução — OpenTelemetry + Prometheus:
FastAPI decorada com @instrument
├── Métricas: latência STT p50/p99, tempo de consenso, taxa de bypass humano
├── Tracing distribuído (OTel): cada decisão crítica gera span
├── Logs estruturados (JSON) → Loki → Grafana
└── Health check: /health (liveness), /ready (readiness: DB, Redis, Deepgram, FS)
- 
Prometheus scrape das métricas do FastAPI.
- 
Grafana dashboard com:
- 
Chamadas ativas / taxa de erro
- 
Latência do pipeline de IA
- 
Número de vezes que o fallback local do STT foi acionado
- 
Consensos negados vs aprovados
C-04: Deepgram → latência de rede externa não contabilizada
Problema: Deepgram pode ter <300ms de processamento, mas a latência de rede até o servidor Deepgram (EUA ou Brasil?) não está especificada. Em Campinas/SP, round-trip para us-east-1 é ~30-50ms; para Deepgram diretamente pode ser maior.
Solução:
- 
Contratar instância Deepgram Dedicated na região mais próxima (sa-east-1) ou usar o proxy deepgram.com/ com rota otimizada.
- 
Medir e documentar: monitor_deepgram_latency.py que faz ping STT a cada 10s.
- 
Se p50_latency > 600ms por mais de 30s → ativar alerta e sugerir fallback.
C-05: Bidirecionalidade do áudio não resolvida
Problema: mod_audio_fork envia áudio RTP puro, mas não está claro como o sistema demuxa quem está falando (morador vs atendente). Sem identificação de speaker, a transcrição é uma sopa de vozes, e o LLM não consegue extrair entidades corretamente (ex: "meu CPF é..." vs "qual seu CPF?").
Solução — Speaker Diarization no STT:
- 
Deepgram suporta diarize: true e retorna speaker em cada utterance.
- 
Fallback local (Whisper.cpp) não faz diarização nativa. Solução: usar pyannote-audio (ou similar) para segmentação de speaker on-premises.
- 
Fluxo:
1. 
mod_audio_fork envia 2 canais (TX do atendente / RX do morador) em canais separados do stream.
2. 
Backend mantém 2 filas no ingestor e rotula cada chunk pelo canal de origem.
3. 
Deepgram/Whisper transcreve com tag de speaker.
🟠 PROBLEMAS DE ALTA SEVERIDADE
H-01: Celery é citado no onboarding mas ignorado na arquitetura
Problema: onboarding.md linha 23 menciona "Celery Worker (Processamento em background)", mas o RFC e o diagrama não o incluem. Isso sugere que processamento pós-chamada (auditoria, sentimento) seria síncrono ou não planejado.
Solução:
- 
Manter Celery (ou substituir por Arq — biblioteca asyncio-native mais leve) para processamento assíncrono.
- 
Auditoria pós-chamada (RF-02, RF-03) roda via Celery, não bloqueia o fluxo em tempo real.
- 
Substituição recomendada: Arq (por arq) — integração natural com Redis, asyncio nativo, sem dependência de RabbitMQ.
H-02: Nenhum suporte a Khomp boards (Hardware Akom)
Problema: O cliente Akom usa hardware Khomp (boards E1/T2). FreeSWITCH precisa configurar wanpipe ou drivers específicos. Sem isso, o SIP Proxy pode não se conectar fisicamente à E1 da operadora.
Solução:
- 
Adicionar Tarefa no actions.md: "Configurar Khomp drivers no container FreeSWITCH (wanpipe, libkhomp)".
- 
Validar roteamento: PBX → Khomp E1 → Operadora vs. Hub → PBX → Khomp.
- 
Teste de integração: chamada entrando da E1 via Khomp precisa ser roteada pelo FreeSWITCH sem queda de áudio.
H-03: Whisper Mode via ESL sem isolamento confirmado
Problema: O RFC assume que uuid_broadcast ou eavesdrop permite injetar áudio apenas na perna do operador. Na prática, o comportamento varia com a topologia: se a ligação é B2BUA, injetar áudio em um leg específico exige uuid_play no UUID correto, e há risco de vazamento para o outro leg (morador ouvir).
Solução — Isolamento por UUID + validação:
- 
Cada perna (leg) da chamada FreeSWITCH tem um UUID único.
- 
O backend mantém {call_id: {agent_uuid: str, customer_uuid: str}}.
- 
Whisper = uuid_play <agent_uuid> /tmp/tts_output.wav.
- 
Filler = uuid_play <customer_uuid> /tmp/aguarde.wav.
- 
Teste obrigatório: gravar ambas as pernas e verificar que o áudio só aparece na perna-alvo.
H-04: PostgreSQL pode não suportar throughput de transcrições em tempo real
Problema: Se cada ligação gera 10-30 inserts/segundo em transcripts (a cada utterance do STT), o PostgreSQL pode ser o gargalo em cenário de múltiplas chamadas simultâneas.
Solução:
- 
transcripts usa append-only em tabela sem índices pesados durante a chamada.
- 
Índices são aplicados após a chamada (em Celery worker).
- 
Usar batch insert: acumular utterances em Redis List durante a chamada, persistir em lote ao final.
- 
Alternativa: TimescaleDB (extensão PostgreSQL para séries temporais) se houver > 50 chamadas simultâneas.
H-05: Segurança da stack on-premises não discutida
Problema: Sistema mission-critical que controla abertura de portas — sem menção a TLS/SRTP, autenticação de API, segregação de rede.
Solução:
1. 
SIP: FreeSWITCH exige <param name="sip-tls" value="true"/> e SRTP obrigatório.
2. 
API: JWT + rate limiting + CORS_ORIGINS restrito.
3. 
Rede: VLAN separada para AI Hub; apenas portas 5060 (TLS), 443 (API), 6379 (Redis, interno) expostas.
4. 
Segredo: opencode secret para gerenciar chaves Deepgram/OpenAI.
H-06: Consenso Multi-Agente com latência não contabilizada
Problema: Grafo Extrator → Revisor → Decisor = 3 chamadas LLM sequenciais. Com GPT-4o-mini (~500ms cada) + overhead de rede = ~2s. Mas se um nó precisar de contexto adicional (ex: buscar POP do condomínio), pode chegar a 4-5s. O RFC menciona "3-5s" mas não propõe otimização.
Solução — Otimização do Grafo:
1. 
Execução paralela: Extrator e Anomalia (fúria) rodam em paralelo (LangGraph permite fan-out).
2. 
Modelo local para revisão simples: Usar um SLM (Phi-3-mini via llama.cpp) para o nó Revisor, que só precisa classificar "autorizado" / "negar" / "encaminhar humano" — não precisa de raciocínio complexo. GPT-4o-mini só para o Decisor final.
3. 
Cache de POPs: POPs de condomínio cacheados em Redis (evita LLM call para buscar regras).
H-07: TTS Local sem fallback
Problema: Se o serviço Piper/Coqui travar, o Whisper Mode e Filler Audio ficam mudos.
Solução:
- 
Piper roda como processo separado com supervisord monitoring (auto-restart).
- 
Fallback: arquivos WAV pré-gravados em disco ("Só um momento...") tocados diretamente via ESL playback().
- 
Health check do TTS Service: /health retorna "ready" apenas se o modelo está carregado.
🟡 PROBLEMAS MÉDIOS
M-01: Diagrama Mermaid mostra mod_audio_fork (UDP/WS) ambíguo
Recomendação: Especificar que o FreeSWITCH envia áudio via WebSocket (não UDP raw), usando media bug ou mod_audio_fork com destino WS. UDP é sem confirmação e pode perder chunks de áudio em rede local congestionada.
M-02: Redis usado para "RTP streaming" — inadequado
Problema: O diagrama sugere .->|UDP/WS| API mas não especifica como o áudio chega ao backend. Assumindo que o backend precisa do áudio PCM em tempo real, Redis PubSub é muito lento e não projetado para stream binário pesado.
Solução: Manter WebSocket entre FreeSWITCH (usando mod_audio_fork com destino ws://backend:8000/audio-stream) e FastAPI. Zero Redis no caminho do áudio.
M-03: Onboarding subestima complexidade de setup
Problema: "docker-compose up -d" em onboarding.md não reflete a complexidade de configurar FreeSWITCH com dialplan de proxy, Khomp drivers, ESL autenticação.
Solução: bootstrap.sh que:
1. 
Gera configs do FreeSWITCH de acordo com a topologia.
2. 
Testa conectividade SIP com o PBX.
3. 
Gera .env com defaults.
Resumo de Decisões para os Dilemas
Dilema
1 — Event Bus
2 — Extração de Entidades
3 — Granularidade Workers
Recomendações de Arquitetura Adicionais
1. 
Adicionar SIPREC como alternativa ao mod_audio_fork — é padrão da indústria e mais fácil de integrar com sistemas de gravação.
2. 
Separar Conference Bridge para Whisper Mode — mais controle que eavesdrop.
3. 
Tooling de desenvolvimento: Usar ngrok para testes locais de webhook com sistema terceiro.
4. 
Testes de caos: chaos-mesh para derrubar containers de IA durante chamada ativa e verificar recuperação.
5. 
Estratégia de deploy: Blue-green com 2 instâncias do FastAPI atrás de nginx (evitar downtime em deploy).
Checklist de Correções Obrigatórias (Pré-codificação)
- 
Adicionar fallback local Whisper.cpp ao STT
- 
Configurar Checkpointer Redis no LangGraph
- 
Adicionar OTel/Prometheus/Grafana ao docker-compose
- 
Documentar latência Deepgram com medição real
- 
Implementar speaker diarization no pipeline de áudio
- 
Substituir Celery por Arq (ou manter Celery mas documentar)
- 
Validar isolamento de áudio Whisper com teste gravado
- 
TimescaleDB ou batch insert para transcripts
- 
TLS/SRTP/JWT na stack
- 
Fallback WAV para TTS
- 
Script bootstrap.sh para ambiente de dev
- 
Teste de caos (restart container com chamada ativa)