# Investigation: AI Hub Audio Strategy (Zenith VoIP)

> Atualizado: 2026-05-17 (Peer Review de 3 LLMs incorporado)

## 1. Alternativas de Interceptação de Áudio

1. **Kamailio + RTPProxy / RTPEngine**:
   - *Prós*: Extremamente escalável, padrão da indústria para SBC e roteamento SIP.
   - *Contras*: O forking nativo para APIs externas é complexo. RTPEngine pode gravar pacotes pcap, mas processar isso ao vivo exige demuxing pesado no backend.
2. **Asterisk + AudioSocket/EAGI**:
   - *Prós*: Facilidade de dialplan, AudioSocket entrega áudio binário direto via socket para o Python.
   - *Contras*: Costuma ser mais pesado para atuar APENAS como B2BUA transparente se comparado ao FreeSWITCH, modificando mais o tráfego SIP.
3. **FreeSWITCH + mod_audio_fork (Vencedor)**:
   - *Prós*: Excelente gerenciamento de media, documentação rica para integrações gRPC/WebSockets, atua como B2BUA nativo flexível, permite re-sampling para L16 (PCM Linear 16kHz) diretamente na extração, facilitando a ingestão pelo STT.
   - *Decisão*: FreeSWITCH envia áudio via **WebSocket** (`ws://backend:8000/audio-stream`) usando `mod_audio_fork`, NÃO via UDP raw nem via Redis. O WebSocket garante entrega ordenada e confirmação.

## 2. Motores de STT (Speech-to-Text)

### Primário: Deepgram (Nuvem)
- Latência líder de mercado (<300ms processamento) com streaming bidirecional via WebSockets.
- Suporta `diarize: true` nativamente para identificação de speaker.
- **Risco:** Dependência de internet. RTT para servidores Deepgram (~30-50ms para sa-east-1) deve ser monitorado.
- **Monitoramento:** Script `monitor_deepgram_latency.py` que faz ping STT a cada 10s. Se `p50_latency > 600ms` por mais de 30s → alerta + fallback.

### Fallback: Whisper.cpp (Local, On-Premises)
- Roda em CPU com quantização (modelo `small` ou `medium`, Q5) com latência ~500ms em CPU moderna.
- Ativado automaticamente via **Strategy Pattern** se Deepgram timeout > 500ms.
- **Limitação:** Não faz diarização nativa. Solução: usar `pyannote-audio` para segmentação de speaker on-premises, ou rotular pelo canal de origem do `mod_audio_fork` (TX do atendente / RX do morador em streams separados).

### Implementação do Fallback
```python
# Strategy Pattern para STT
class STTStrategy(ABC):
    async def transcribe_stream(self, audio_chunks) -> AsyncIterator[Utterance]: ...

class DeepgramSTT(STTStrategy): ...     # primário, nuvem
class WhisperCppSTT(STTStrategy): ...   # fallback, local

class AutoFallbackSTT(STTStrategy):
    """Se deepgram timeout > 500ms, alterna para WhisperCpp automaticamente."""
```

## 3. Speaker Diarization

Sem identificar quem falou, a transcrição é uma "sopa de vozes". O LLM não consegue distinguir "meu CPF é..." (morador) de "qual seu CPF?" (atendente).

### Abordagem em 2 Camadas
1. **Camada de Canal (preferida):** `mod_audio_fork` envia 2 canais separados (TX do atendente / RX do morador). O backend mantém 2 filas no ingestor e rotula cada chunk pela origem. Zero latência adicional.
2. **Camada de IA (backup):** Deepgram com `diarize: true` rotula cada utterance com `speaker: 0/1`. Funciona mesmo em canal mono.

## 4. Event Bus — Redis Streams vs Alternativas

| Tecnologia | Latência | Persistência | Complexidade | Decisão |
|------------|----------|-------------|--------------|---------|
| Redis Pub/Sub | ~0ms | ❌ Fire-and-Forget | Baixa | Descartado (perda de dados inaceitável) |
| Redis Streams | ~0ms | ✅ ACK + Consumer Groups + DLQ | Média | **Escolhido** |
| RabbitMQ | ~1-5ms | ✅ Total | Alta | Descartado (peso desnecessário com Redis Streams) |
| Kafka | ~5-10ms | ✅ Total | Muito alta | Descartado (overengineering para on-premises) |

### Por que Redis Streams?
- Unifica o barramento: um broker só para tempo real E pós-chamada.
- Consumer Groups garantem que mensagens de auditoria pós-chamada só são removidas após ACK do worker.
- `XADD` + `XREADGROUP` + `XACK` = entrega garantida sem o peso de um broker externo.
- Redis já é obrigatório na stack (checkpointing do LangGraph, state do WebSocket).

## 5. Extração de Entidades em Tempo Real (Triage Mista)

```
Deepgram/Whisper Stream → [Camada 1: Regex/spaCy] → padrão detectado? 
                                    │                         │
                                  Não → descarta chunk        Sim
                                                              │
                                                    [Camada 2: LLM Local]
                                                    (Mistral 7B via Ollama)
                                                              │
                                                    JSON validado → WebSocket → Painel
```

- **Camada 1 (Regex/spaCy):** Custo zero, ~0ms. Detecta padrões fixos (CPF: `\d{3}\.?\d{3}\.?\d{3}-?\d{2}`, Placa, RG). Filtra ~90% dos chunks sem custo.
- **Camada 2 (LLM Local):** Mistral 7B via Ollama. Só invocado quando Camada 1 detecta suspeita. Higieniza dados hesitados ("nove dois... não, oito dois"). SLA: ~300-500ms.
- **Senhas:** EXCLUÍDAS do pipeline. Coletadas via DTMF com mascaramento. Zero persistência.

## 6. Consenso Multi-Agente (Orquestração LangGraph)

### Escopo do Consenso
O fluxo de 3 nós (Extrator → Revisor → Decisor) é **reservado apenas para ações que mexem no mundo físico** (abrir porta, liberar acesso via API). Extração de entidades para Agent Assist usa saída direta sem consenso — decisão final é do operador.

### Otimização de Latência do Grafo
1. **Fan-out paralelo:** Extrator e Detector de Anomalia (fúria) rodam em paralelo no LangGraph.
2. **SLM para Revisor:** Usar modelo local pequeno (Phi-3-mini via llama.cpp ou Mistral 7B) para o nó Revisor, que só classifica "autorizado / negar / encaminhar humano". GPT-4o-mini reservado para Decisor final.
3. **Cache de POPs:** Regras de condomínio cacheadas em Redis (evita chamada LLM para buscar procedimentos).

### Checkpointing para Resiliência (CR-02)
```python
from langgraph.checkpoint.redis import RedisSaver

redis_saver = RedisSaver(redis_client)
graph = builder.compile(checkpointer=redis_saver)
# A cada transição de nó, estado é salvo automaticamente.
# Em crash/restart, grafo é recuperado pelo call_id.
```
- Custo: ~50μs por checkpoint em Redis local (desprezível).
- Em crash do container, chamadas ativas recuperam estado do último nó completado.

## 7. Whisper Mode — Isolamento via UUID

### Mecânica de Isolamento
Cada perna (leg) da chamada FreeSWITCH tem um UUID único. O backend mantém:
```python
call_legs = {
    "call_id_123": {
        "agent_uuid": "uuid-atendente-xxx",
        "customer_uuid": "uuid-morador-yyy"
    }
}
```
- **Whisper** = `uuid_play <agent_uuid> /tmp/tts_output.wav` (só o atendente ouve)
- **Filler** = `uuid_play <customer_uuid> /tmp/aguarde.wav` (só o morador ouve)
- **Teste obrigatório:** Gravar ambas as pernas separadamente e verificar que o áudio injetado aparece SOMENTE na perna-alvo.

## 8. Text-to-Speech (TTS) Local

### Motor Primário
- **Piper TTS**: Extremamente rápido, feito em C++, roda perfeito em CPU sem GPU, vozes muito boas (`pt-br-edresson-low`).
- **Coqui TTS (XTTS)**: Permite clonar uma voz (3 segundos de amostra). Roda melhor com GPU local.
- A voz sintética deve emitir credibilidade e firmeza (essencial para Segurança Física).

### Fallback para WAV Pré-gravados
Se o serviço TTS travar:
- Arquivos WAV pré-gravados em disco ("Só um momento...", "Estou verificando...", etc.) tocados diretamente via ESL `playback()`.
- Health check do TTS Service: `/health` retorna "ready" apenas se o modelo está carregado.
- Piper roda como processo separado com `supervisord` para auto-restart.

## 9. Worker Pós-Chamada — Arq

| Critério | Celery | Arq (Escolhido) |
|----------|--------|------------------|
| Asyncio nativo | ❌ | ✅ |
| Broker | Redis ou RabbitMQ | Redis (nativo) |
| Peso | Pesado | Muito leve |
| Integração Redis Streams | Manual | Natural |
| Comunidade | Grande | Menor (mas suficiente) |

Arq consome eventos do Redis Streams para: Auditoria pós-chamada, Análise de sentimento, Relatórios de checklist.

## 10. Segurança da Stack On-Premises

| Camada | Requisito | Implementação |
|--------|-----------|---------------|
| SIP | Criptografia de sinalização e media | FreeSWITCH com `sip-tls=true` + SRTP obrigatório |
| API | Autenticação e rate limiting | JWT + rate limiting + CORS restrito |
| Rede | Segregação | VLAN separada para AI Hub |
| WAF | Proteção HTTP | BunkerWeb WAF (já em uso pelo cliente) |
| Segredos | Gestão de chaves | Variáveis de ambiente via `.env` seguro |

## 11. Observabilidade

```
FastAPI (@instrument decorator)
├── Métricas: latência STT p50/p99, tempo de consenso, taxa de bypass humano, taxa de fallback
├── Tracing: OpenTelemetry spans por decisão crítica
├── Logs: JSON estruturado → Loki → Grafana
└── Health checks:
    ├── /health (liveness: processo vivo)
    └── /ready (readiness: DB, Redis, Deepgram, FreeSWITCH, TTS)
```

## 12. Design Patterns Aplicados (Arquitetura Python)

- **Strategy**: `STTService` (Deepgram/Whisper.cpp), `TTSService` (Piper/Coqui), `LLMService` (OpenAI/Mistral).
- **Repository**: `CallRepository`, `TranscriptRepository` centralizam SQLAlchemy/asyncpg.
- **Observer**: Backend emite eventos de domínio (`CallStarted`, `TranscriptReceived`, `InsightGenerated`). Handlers e WebSockets se inscrevem via Redis Streams.
- **Factory Method**: Instancia pipelines de áudio baseado no Tenant ou tipo de ligação.

## 13. Multi-Instância e Alta Disponibilidade

```
BunkerWeb WAF (Load Balancer)
    ├── FastAPI Instance 1 (call_ids com hash par)
    └── FastAPI Instance 2 (call_ids com hash ímpar)
         └── Ambas compartilham: Redis, PostgreSQL, FreeSWITCH
```
- Sharding por `hash(call_id) % N` via BunkerWeb sticky sessions.
- Um crash afeta 50% das chamadas (não 100%).
- Checkpointing Redis permite recuperação do estado ao reiniciar.

## 14. Desktop Widget — Tauri

### Por que não browser/Electron?
O operador da Akom já tem a tela lotada com GEAR (sistema de portaria), câmeras, telefone softphone. Abrir mais uma aba de browser ou um Electron (~200MB RAM com Chromium embutido) é inviável.

### Decisão: Tauri (Rust + HTML/CSS/JS)
- **WebView2 nativo do Windows 10/11** — não embala Chromium, consome ~15MB de RAM.
- **Always-on-top** com `decorations: false` (janela sem borda) + `always_on_top: true`.
- **System Tray** — quando não há chamada ativa, o widget fica como ícone na bandeja do Windows.
- **Auto-show/Auto-hide** — WebSocket recebe evento `call.started` → widget aparece; `call.ended` → widget minimiza.

### Layout do Widget MVP
```
┌─────────────────────────────────────┐
│ 🟢 Zenith AI · Visitante Detectado  │  ← Tipo de atendimento (detectado por IA)
├─────────────────────────────────────┤
│ ☑ Pedir nome completo              │
│ ☐ Verificar autorização no app     │  ← Checklist POP (dinâmico por condomínio)
│ ☐ Solicitar documento              │
│ ☐ Confirmar com morador            │
├─────────────────────────────────────┤
│ [🎙 Copiloto]  [⏸ Pausar IA]      │  ← Barra de controle
│ STT: Deepgram ✅ · Fúria: Baixa    │  ← Status em tempo real
└─────────────────────────────────────┘
```

### Funcionalidades Futuras (NÃO no MVP)
- Transcrição ao vivo rolando no widget.
- Script guiado por IA (o que o operador deve falar a seguir).
- Dashboard de histórico de chamadas.

### Stack de Linguagens do Projeto (Consolidada)
| Componente | Linguagem | Justificativa |
|------------|-----------|---------------|
| Backend (FastAPI) | Python 3.12+ (POO) | Ecossistema de IA, asyncio, LangGraph |
| Worker Pós-chamada (Arq) | Python 3.12+ (POO) | Mesmo ecossistema, integra com Redis |
| FreeSWITCH configs | XML + Lua | Padrão FreeSWITCH |
| Desktop Widget (Tauri) | Rust (shell) + HTML/CSS/JS (UI) | Leve, overlay nativo, WebView2 |
| LLM Local | Mistral 7B via Ollama | Container Docker, API REST |
| TTS Local | Piper TTS (C++) | Container Docker, API REST |

