# Glossário e Regras de Domínio — zenith-voip

> Gerado pelo Detective — 2026-06-19
> **Re-extração incremental — 2026-07-27** (base `48da5b1` → `0658157`)
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA
> Arqueologia Git: ✅ **agora disponível** — 37 commits desde a extração anterior
> (a lacuna "projeto sem repositório Git local" de 2026-06-19 está resolvida)

## Glossário

| Termo | Definição |
|-------|-----------|
| **Chamada (Call)** | Sessão telefônica entre agente e cliente, com direção (inbound/outbound) e status (ringing/in_progress/completed/failed) |
| **Transcrição (Transcript)** | Segmento de texto transcrito do áudio de uma chamada, com canal (tx/rx), speaker, confidence e timestamps |
| **Insight (CallInsight)** | Análise pós-chamada: sentimento, entidades extraídas, detecção de anomalias, consenso, POPs |
| **PBX** | Central telefônica vinculada a um tenant (cliente do sistema) |
| **Tenant** | Inquilino — cliente com schema PostgreSQL isolado e seus próprios PBXs |
| **POP** | Procedimento Operacional Padrão — checklist que o agente deve seguir durante a chamada |
| **STT** | Speech-to-Text: transcrição de áudio para texto |
| **TTS** | Text-to-Speech: síntese de voz a partir de texto |
| **ESL** | Event Socket Layer — protocolo do FreeSWITCH para eventos e comandos |
| **Ramal SIP** | Extensão SIP do agente no PBX, usada para auto-link |
| **Auto-link** | Vínculo automático entre o widget WebSocket e o ramal SIP do agente via IP |
| **Manual Linkage (\*88)** | Código discado no softphone para vincular o widget ao ramal |
| **Whisper Mode** | Funcionalidade que permite ao sistema "sussurrar" informações no ouvido do agente via TTS |
| **Filler Audio** | Áudio de preenchimento tocado para o cliente enquanto o sistema processa |
| **Consenso** | Validação em 3 ciclos (extração → revisão → decisão) via LangGraph |
| **Anomalia** | Detecção de tom agressivo ou estresse na fala do cliente |
| **Fury Score** | Pontuação baseada em keywords de fúria em português (13 termos) |
| **Schema-per-tenant** | Estratégia de multitenancy onde cada cliente tem um schema PostgreSQL isolado |

## Regras de Domínio

### Chamadas

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R01 | Chamada só pode ser inbound ou outbound | `models.py:13-15` | 🟢 |
| R02 | Chamada nasce como in_progress e transita para completed ou failed | `models.py:18-22` | 🟢 |
| R03 | Chamada pertence a um schema de tenant específico | `database.py:33-37` | 🟢 |
| R04 | Duração da chamada é calculada em segundos entre started_at e ended_at | `models.py:68-69` | 🟢 |

### PBXs

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R05 | PBX sempre pertence a um tenant (FK com CASCADE) | `models.py:44` | 🟢 |
| R06 | Apenas tenant_admin pode criar/listar PBXs | `auth.py:35-40` | 🟢 |
| R07 | Porta SIP padrão é 5060 (default do modelo de aplicação; a topologia FreeSWITCH aceita também 7060/5062 na camada de entrada — ver `telephony/design.md#3`, feature `006-registro-porta-vitalpbx`) | `models.py:48` | 🟢 |

### STT

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R08 | Deepgram é o provider primário de STT | `stt_autofallback.py:10` | 🟢 |
| R09 | Fallback para Whisper.cpp se timeout > 500ms | `stt_autofallback.py:14-15` | 🟢 |
| R10 | Fallback também ocorre se confidence <= 0.3 | `stt_autofallback.py:20` | 🟢 |
| R11 | Modelo Deepgram: nova-2, português, diarizado | `stt_deepgram.py:15-19` | 🟢 |

### TTS

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R12 | Piper TTS é o provider primário | `tts_service.py:6` | 🟢 |
| R13 | Se Piper falhar, usa WAV local do disco | `tts_fallback.py:13-17` | 🟢 |

### Detecção de Anomalias

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R14 | Anomalia detectada se fury_score + stress_score >= 3 | `anomaly_detector.py:29` | 🟢 |
| R15 | Severidade danger se score >= 5, warning se >= 3 | `anomaly_detector.py:33-34` | 🟢 |
| R16 | 27 keywords de fúria em português | `anomaly_detector.py:6-13` | 🟢 |
| R17 | Padrões de estresse: ALL CAPS, !! múltiplos, palavras repetidas | `anomaly_detector.py:15-18` | 🟢 |

### Consenso (LangGraph)

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R18 | Consenso executa em até 3 ciclos (extract → review → decide) | `consensus_graph.py:70-72` | 🟢 |
| R19 | Decisão rejeitada se sentiment_score < -0.3 | `consensus_graph.py:65` | 🟢 |
| R20 | Dados sensíveis (cartão de crédito) passam por sanitização via LLM | `consensus_graph.py:58-59` | 🟢 |

### Dados Sensíveis

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R21 | CPF, RG e placa disparam suspeita | `regex_layer.py:32-35` | 🟢 |
| R22 | Cartão de crédito é marcado como sensitive | `regex_layer.py:15` | 🟢 |
| R23 | LLM roda localmente (Ollama) — nenhum dado enviado para nuvem | `llm_layer.py:6` | 🟢 |

### SIP e Telefonia

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R24 | Mapeamento SIP→IP expira em 1 hora | `esl_client.py:179-184` | 🟢 |
| R25 | Código *88 dispara linkage manual | `esl_client.py:136-137` | 🟢 |
| R26 | Reconexão ESL automática com backoff de 2s | `esl_client.py:86-88` | 🟢 |
| R27 | Widget tenta auto-reconnect a cada 3s | `ws-client.js:33` | 🟢 |

### Áudio e Armazenamento

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| ~~R28~~ | ~~Retenção de áudio: 90 dias~~ → substituída por R36 | — | ⚠️ obsoleta |
| ~~R29~~ | ~~Cleanup roda diariamente às 03:00~~ → substituída por R37 | — | ⚠️ obsoleta |
| ~~R30~~ | ~~Delete S3 em lotes de até 1000 objetos~~ → S3 removido | — | ⚠️ obsoleta |
| ~~R31~~ | ~~Bucket S3 nomeado como {prefix}-{tenant_id}~~ → S3 removido | — | ⚠️ obsoleta |
| R32 | Instância FastAPI identificada por INSTANCE_ID | `config.py:5` | 🟢 |

### API e Segurança

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R33 | Rate limit: 100 requisições por IP a cada 60s | `rate_limit.py:7-8` | 🟢 |
| R34 | JWT expira em 60 minutos | `config.py:23` | 🟢 |
| R35 | Admin role = "tenant_admin" | `auth.py:36` | 🟢 |

---

## Regras novas — re-extração 2026-07-27

### Gravação e retenção

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R36 | Retenção de gravação em produção: **~1 hora** (`AUDIO_RETENTION_DAYS=0.0417`) | `docker-compose.app.yml` | 🟢 |
| R37 | Cleanup roda **a cada 15 minutos** (`minute={0,15,30,45}`) | `audio_cleanup.py:59-62` | 🟢 |
| R38 | Gravação vive em **tmpfs de 512 MB** (RAM), nunca em disco nem em nuvem | `docker-compose.app.yml` | 🟢 |
| R39 | Cada canal vira um **MP3 mono 8 kHz** separado (`tx.mp3`, `rx.mp3`) — nunca misturado | `audio_uploader.py:11,25-33` | 🟢 |
| R40 | Falha de conversão preserva o `.raw` (`uploaded_raw_only`) — degrada, não perde | `audio_uploader.py:52-55` | 🟢 |
| R41 | Layout de gravação: `RECORDINGS_PATH/<tenant_id>/<call_id>/<channel>.mp3` | `audio_uploader.py:44-46` | 🟢 |

### Captura de áudio

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R42 | Captura é disparada pela **aplicação via ESL** no CHANNEL_ANSWER, não pelo dialplan | `esl_client.py:224-238` | 🟢 |
| R43 | Frame estéreo é dividido por índice: pares = `tx` (agente), ímpares = `rx` (cliente) | `ingestor.py:86-94` | 🟢 |
| R44 | WebSocket de áudio exige `call_id` registrado via ESL, senão fecha com **4401** | `ingestor.py:27-36` | 🟢 |
| R45 | Frame de texto do `mod_audio_stream` é ignorado, não bufferizado como áudio | `ingestor.py:44-48` | 🟢 |

### Ciclo de vida da chamada

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R46 | Linha `Call` só é criada se `tenant_id` vier populado no evento — senão a chamada não é registrada | `esl_client.py:219` | 🟢 |
| R47 | Chamada nasce `in_progress`/`inbound`; `ringing` e `failed` nunca são atribuídos | `services/calls.py:16-17` | 🟢 |
| R48 | `duration_seconds` é calculado no hangup, não medido durante a chamada | `services/calls.py:32` | 🟢 |
| R49 | Hangup de chamada sem registro prévio é ignorado em silêncio | `services/calls.py:26-28` | 🟢 |
| R50 | Escrita em schema de tenant exige commit explícito na Connection | `database.py:24-29` | 🟢 |
| R51 | Schema do tenant segue o padrão `tenant_<tenant_id>` | `services/calls.py:7-8` | 🟢 |

### Operação e infraestrutura

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R52 | Apenas `INSTANCE_ID == 1` consome o event stream do ESL (evita duplicidade) | `main.py:26,34` | 🟢 |
| R53 | Comandos ESL usam socket próprio, nunca o do event stream | `esl_client.py:58-82` | 🟢 |
| R54 | FreeSWITCH só é considerado saudável se `mod_audio_stream` estiver carregado | `docker-compose.app.yml` | 🟢 |
| R55 | Todo recurso Docker do projeto usa prefixo `zenith-` / `zenith_`; recursos fora dele são intocáveis | `CLAUDE.md` | 🟢 |
| R56 | Portas da API publicadas apenas em `127.0.0.1` no host | `docker-compose.app.yml` | 🟢 |
| R57 | Estado do consenso é in-process e volátil (`MemorySaver`) | `consensus_graph.py:28-34` | 🟢 |

### Sidecar de IP externo

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| R58 | No boot o watcher sempre aplica o IP, mesmo sem mudança detectada | `sidecar/watcher.py:139-144` | 🟢 |
| R59 | A comparação é contra o `Ext-SIP-IP` anunciado pelo FreeSWITCH, não contra o último IP visto | `sidecar/watcher.py:145` | 🟢 |
| R60 | Escrita de `vars-external-ip.xml` é atômica (`.tmp` + `os.replace`) | `sidecar/watcher.py:45-48` | 🟢 |
| R61 | Descoberta de IP tem fallback por rota de saída (`getsockname`) quando o HTTP falha | `sidecar/watcher.py:26-34` | 🟢 |

## TODOs e FIXMEs

| Local | Conteúdo | Implicação |
|-------|----------|------------|
| ~~`src/audio/ingestor.py:70-71`~~ | ~~`_detect_channel()` retorna "tx" hardcoded~~ | ✅ **RESOLVIDO** em 2026-07 — `_split_stereo_frame()` faz o de-interleaving real |
| `src/workers/post_call.py:7-12` | `analyze_sentiment()` e `audit_procedure()` retornam stubs | 🔴 Análise de sentimento e auditoria pós-chamada continuam não implementadas |
| `src/audio/ingestor.py:59` | `AudioChunk.timestamp` sempre `0.0` | 🔴 Eixo temporal do áudio não é reconstruível a partir do buffer |
| `src/services/tts_service.py:19-20` | `voice` e `speaker_id` na assinatura mas ignorados | 🔴 Voz é fixa em `PIPER_VOICE_PATH` |
| `freeswitch/conf/vars.xml` | `tenant_id`/`pbx_id` fixos como variáveis globais | 🔴 Bloqueia multi-tenant real — hoje só o tenant Akom funciona |
| `alembic/versions/001_initial.py` | tenant_id na tabela calls (removido na v003) | 🟡 Mudança de abordagem: de coluna tenant_id para schema separado |
