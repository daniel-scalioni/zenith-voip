# Análise de Código — zenith-voip

> Gerado pelo Archaeologist — 2026-06-19
> **Re-extração incremental — 2026-07-27** (base `48da5b1` → `0658157`, 37 commits, +1692/−253)
> Nível de documentação: completo
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Sumário

**Zenith AI Audio Hub** é um sistema de IA para transcrição e análise de chamadas VoIP em
tempo real. Escrito em Python (FastAPI), integra-se ao FreeSWITCH via ESL, usa Deepgram +
Whisper.cpp para STT com fallback automático, Ollama (Mistral 7B) para LLM local, Piper TTS
**in-process** para síntese de voz, e PostgreSQL com multitenancy físico.

**O que mudou desde a extração anterior:** o pipeline de captura de áudio saiu do papel e
passou a funcionar de ponta a ponta em chamada real. As três mudanças estruturantes:

1. **S3 foi removido.** Gravação vai para filesystem local em **tmpfs (RAM)**, convertida
   para MP3 por canal, com retenção de ~1 hora.
2. **A captura deixou de ser responsabilidade do dialplan.** `mod_audio_fork` foi
   substituído por `mod_audio_stream`, e o `uuid_audio_stream` passou a ser disparado pela
   aplicação, via ESL, no `CHANNEL_ANSWER`.
3. **O ESLClient passou a ser realmente conectado.** Antes ele existia mas nunca era
   iniciado — nenhum handler de evento rodava em produção.

## Arquitetura Geral

```
[Interfone/Softphone] →SIP→ [FreeSWITCH B2BUA] →SIP→ [VitalPBX upstream]
                                   ↓ ESL (2 sockets: eventos + comandos)
                            [FastAPI instância 1]  ← só a 1 consome ESL
                                   ↓ WS /audio-stream/{call_id}
                            [AudioIngestor] → de-interleaving tx/rx
                                   ↓
              [Redis Streams] ←→ [Workers ARQ: uploader, cleanup, transcript]
                                   ↓                        ↓
                     [PostgreSQL multitenant]     [tmpfs /data/recordings → mp3]

[zenith-ip-watcher] → vars-external-ip.xml → reloadxml + sofia restart
```

### Fluxo Principal de uma Chamada (atualizado)

1. **FreeSWITCH** recebe a chamada; o dialplan (`zenith_audio_fork`) seta
   `zenith_tenant_id`/`zenith_pbx_id` a partir de variáveis globais e faz bridge para o
   gateway upstream do ramal.
2. **ESLClient** (só em `INSTANCE_ID==1`) recebe `CHANNEL_ANSWER`, registra os metadados no
   `AudioIngestor` — **isso é o que autoriza o WebSocket daquele `call_id`** —, cria a linha
   `Call` no schema do tenant e dispara `bgapi uuid_audio_stream`.
3. **FreeSWITCH** abre o WebSocket em `/audio-stream/{call_id}` e envia PCM16 estéreo 8 kHz.
4. **AudioIngestor** faz de-interleaving (`tx` = pares, `rx` = ímpares), bufferiza e publica
   um evento por canal no Redis Stream `call:events`.
5. **Workers ARQ** consomem: STT (Deepgram → fallback Whisper), extração, anomalias.
6. **Transcripts** bufferizados no Redis e persistidos em lote no PostgreSQL.
7. **ConsensusGraph** (LangGraph, `MemorySaver`) valida entidades em até 3 ciclos.
8. **Resultados** enviados via WebSocket para o Widget Tauri do operador.
9. **CHANNEL_HANGUP**: finaliza a linha `Call` (status, `ended_at`, `duration_seconds`),
   agrupa os chunks por canal e enfileira o upload.
10. **zenith-arq-uploader** grava `.raw` e converte para MP3 mono por canal.
11. **Cleanup a cada 15 min**: remove gravações com mais de ~1 hora do tmpfs.

## Módulos Analisados (13)

### 1. api — Interface REST + WebSocket
- FastAPI com lifespan que **agora inicia o ESLClient** (só `INSTANCE_ID==1`) 🆕
- Endpoint WebSocket `/audio-stream/{call_id}` registrado no app 🆕
- JWT auth com RBAC (agent / tenant_admin), rate limit in-memory (100 req/60s por IP)
- CRUD de PBXs, WebSocket Agent Assist com auto-link SIP, webhook dispatcher
- Portas 8001/8002 publicadas apenas em `127.0.0.1` 🆕
- **🟢 6 arquivos, ~365 linhas**

### 2. ai — Inteligência Artificial
- Detecção de anomalias de tom (keywords de fúria + padrões de estresse, threshold 3)
- Grafo de consenso LangGraph: extractor → reviewer → decider (até 3 iterações)
- 🔄 Checkpointer trocado de `RedisSaver` para **`MemorySaver`** (conflito `redis<6` do arq
  vs `redis>=6.2` do `langgraph-checkpoint-redis`) — estado volátil e por processo
- Cache Redis de POPs (TTL 1h)
- **🟢 3 arquivos, 191 linhas**

### 3. audio — Ingestão de Áudio
- 🆕 **Guard de autorização**: `call_id` não registrado via ESL → fecha com código 4401
- 🆕 **De-interleaving PCM16 estéreo** substituiu o `_detect_channel()` hardcoded
- Tolera o frame de texto de controle do `mod_audio_stream`
- Publica um evento por canal no Redis Stream
- **🟢 1 arquivo, 95 linhas**

### 4. database — Persistência
- Multitenancy físico: schemas PostgreSQL isolados por tenant (`tenant_<id>`)
- 6 modelos ORM; 🆕 `Boolean` explícito em 4 colunas; `metadata` → `extra_metadata`
- 🆕 `get_tenant_db` faz `conn.commit()` explícito (antes: rollback silencioso)
- Migrations via Alembic; provisionamento por `scripts/provision_tenant.py` 🆕
- **🟢 2 arquivos, 184 linhas**

### 5. events — Event Bus *(sem alteração)*
- Redis Streams: publish, consume, ack, create_group; streams `call:events` e `call:post`
- **🟢 1 arquivo, 38 linhas**

### 6. extraction — Extração de Dados *(sem alteração de código)*
- 6 padrões regex (CPF, RG, telefone, placa, CEP, cartão); cartão marcado como sensitive
- LLM local (Ollama Mistral 7B) para correção contextual
- ⚠️ `python-brasilcpf` saiu do `requirements.txt` — validar se algo dependia dele
- **🟢 2 arquivos, 67 linhas**

### 7. observability — Telemetria *(sem alteração de código)*
- OpenTelemetry + FastAPI instrumentation, 16 métricas Prometheus, endpoint `/metrics`
- ⚠️ As métricas de S3 agora medem um subsistema que não existe mais
- **🟢 2 arquivos, 192 linhas**

### 8. services — Serviços de IA
- Strategy Pattern: STTStrategy, TTSStrategy, LLMStrategy; Repository genérico
- AutoFallback STT: Deepgram → Whisper.cpp (timeout 500ms, confidence > 0.3)
- 🔄 **PiperTTS in-process** (`PiperVoice.load` + `lru_cache` + `asyncio.to_thread`)
- 🆕 `calls.py`: `create_call_record` / `finalize_call_record`
- **🟢 7 arquivos, ~291 linhas**

### 9. telephony — Integração FreeSWITCH
- 🆕 **Duas conexões ESL** (eventos e comandos), com lock no canal de comandos
- 🆕 Parser respeitando `Content-Length` (antes: split por `\n\n`, que corrompia eventos)
- 🆕 Handler `CHANNEL_HANGUP`; `_start_audio_capture` via `bgapi uuid_audio_stream`
- Reconexão automática (backoff 2s); timeout de leitura 30s → 300s
- Mapeamento SIP/IP no Redis (TTL 1h); `*88` para manual linkage; Whisper Mode; filler audio
- ⚠️ `greenswitch` saiu do `requirements.txt` — ESL é socket TCP bruto
- **🟢 3 arquivos, 363 linhas**

### 10. workers — Background Jobs
- 🔄 **S3 removido**: gravação em `RECORDINGS_PATH` (tmpfs) + conversão MP3 via ffmpeg
- 🔄 Cleanup: cron 03:00 diário → **a cada 15 min**; `os.walk` em vez de listagem S3
- 🆕 `enqueue_recording_upload` + container `zenith-arq-uploader`
- Buffer de transcrições no Redis com flush batch
- 🔴 `post_call.py` continua stub
- **🟢 4 arquivos, 231 linhas**

### 11. widget — Desktop Widget *(sem alteração)*
- Tauri (Rust) sempre-on-top, 320x500, transparente; POPs, transcrição, alertas, copiloto
- **🟢 4 arquivos**

### 12. infra — Infraestrutura
- 🆕 Namespace obrigatório `zenith-` / `zenith_` em todo recurso Docker
- 🔄 FreeSWITCH passou a **build próprio** com `mod_audio_stream` e healthcheck de módulo
- 🆕 tmpfs `zenith_recordings_tmpfs` (512 MB); 🆕 `zenith-arq-uploader`; 🆕 `zenith-ip-watcher`
- ❌ `piper-tts` removido; subnet `172.20` → `172.21`
- **🟢 12+ arquivos de configuração**

### 13. sidecar — Watcher de IP externo 🆕 (módulo novo)
- Poll do IP público (HTTP + fallback `getsockname`), escrita atômica de
  `vars-external-ip.xml`, `reloadxml` + `sofia profile upstream restart` via ESL bruto
- Log estruturado JSON por ciclo (`ip_anterior`, `ip_atual`, `acao_tomada`)
- **🟢 4 arquivos, 243 linhas**

## Algoritmos-Chave

| Algoritmo | Módulo | Descrição |
|-----------|--------|-----------|
| AutoFallback STT | services | Deepgram com timeout 500ms → Whisper.cpp |
| SIP Auto-Link | api | IP do WS → Redis → ramal SIP |
| Consensus Graph | ai | LangGraph 3 nós, até 3 iterações, estado in-process |
| Anomaly Detection | ai | Keywords + padrões estresse, threshold 3 |
| Multitenancy | database | Schema PostgreSQL por tenant (`tenant_<id>`) |
| ESL Reconexão | telephony | Auto-reconnect com backoff 2s, timeout 300s |
| **Framing ESL por Content-Length** 🆕 | telephony | Headers até linha em branco + N bytes de corpo |
| **De-interleaving PCM16** 🆕 | audio | `samples[0::2]` = tx, `samples[1::2]` = rx |
| **Cleanup por mtime** 🔄 | workers | `os.walk` + cutoff, cede o loop a cada 1000 arquivos |
| **Conversão MP3** 🆕 | workers | ffmpeg s16le 8k mono → libmp3lame, por canal |
| **Descoberta de IP externo** 🆕 | sidecar | HTTP + fallback `getsockname("8.8.8.8")` |

## Algoritmos que deixaram de existir

| Algoritmo (2026-06-19) | Situação |
|---|---|
| S3 Cleanup (lotes de 1000, retenção 90 dias) | Removido com o `boto3` |
| `_detect_channel()` retornando `"tx"` fixo | Substituído pelo de-interleaving real |
| Registration forwarding via dialplan (`sip_forward_host`) | Extensão removida do dialplan |
| `bypass_to_pbx` com `bypass_media=true` | Removida — mídia não pode ser bypassada se o FreeSWITCH precisa capturá-la |

## Totalização

| Métrica | 2026-06-19 | 2026-07-27 |
|---------|---|---|
| Arquivos de código (src) | 32 | 34 (+ 4 em `sidecar/`) |
| Arquivos de teste | 7 | 10 |
| Total linhas de código | ~1.800 | ~3.200 |
| Dependências Python | 31 pacotes | 26 pacotes (−5) |
| Containers Docker | 14 | 15 (+uploader, +ip-watcher, −piper-tts) |
| Tabelas no banco | 6 | 6 |
| Módulos | 12 | **13** (+ `sidecar`) |
