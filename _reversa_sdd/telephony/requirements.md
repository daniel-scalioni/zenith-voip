---
spec:
  component: esl-integration
  layer: telephony
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton, observer]
  inputs:
    - {name: esl_event, type: json, from: freeswitch/mod_event_socket}
  outputs:
    - {name: uuid_audio_stream, type: esl_bgapi, to: freeswitch}
    - {name: call_record, type: row, to: services/calls}
    - {name: upload_recording_batch, type: arq job, to: workers/audio_uploader}
    - {name: stream_metadata, type: dict, to: audio/ingestor}
  dependencies:
    - {component: calls, layer: services}
    - {component: audio_uploader, layer: workers}
    - {component: ingestor, layer: audio}
    - {component: redis_streams, layer: events}
  events_produced: [SOFIA_REGISTER, CHANNEL_ANSWER, CHANNEL_HANGUP]
  updated_at: 2026-07-27
---

# Telephony — Integração FreeSWITCH

> Gerado pelo Writer — 2026-06-19
> **Revisado na re-extração incremental — 2026-07-27** (deltas D-01/D-12)

## Visão Geral

Integração com FreeSWITCH via Event Socket Layer (ESL): conexão, eventos de chamada,
**orquestração do ciclo de vida da chamada**, disparo da captura de áudio, mapeamento SIP,
whisper mode e filler audio.

O `ESLClient` deixou de ser um mero ouvinte de eventos: ele agora cria e finaliza a linha
`Call`, autoriza o WebSocket de áudio e dispara o `uuid_audio_stream` (ADR-010).

## Responsabilidades

- Manter **duas conexões ESL independentes**: uma para o event stream, outra para `api`/`bgapi`
- Conectar com reconexão automática (backoff 2s) e consumir a saudação `auth/request`
- Fazer o framing correto dos eventos por `Content-Length`
- Escutar `CHANNEL_CREATE`, `CHANNEL_ANSWER`, `CHANNEL_HANGUP`, `SOFIA_REGISTER`, `SOFIA_UNREGISTER`
- No `CHANNEL_ANSWER`: registrar metadados no ingestor, criar a linha `Call`, disparar a captura
- No `CHANNEL_HANGUP`: finalizar a linha `Call` e enfileirar a gravação
- Mapear IP ↔ ramal SIP no Redis (TTL 1h)
- Implementar whisper mode (TTS no canal do agente) e filler audio
- Detectar código `*88` para linkage manual

## Regras de Negócio

| Regra | Confiança |
|---|---|
| Reconexão automática com backoff de 2s | 🟢 |
| `*88` é código de linkage manual | 🟢 |
| SIP mappings expiram em 1h | 🟢 |
| Comandos ESL usam socket próprio, nunca o do event stream | 🟢 |
| Captura de áudio é disparada pela aplicação no `CHANNEL_ANSWER`, não pelo dialplan | 🟢 |
| Linha `Call` só é criada se `tenant_id` vier populado no evento | 🟢 |
| Gravação só é enfileirada se houver chunks no buffer | 🟢 |
| Falha de um handler não derruba o event loop | 🟢 |
| Widget tenta auto-reconnect a cada 3s | 🟢 |

## Requisitos Funcionais

| ID | Requisito | Prioridade | Status |
|----|-----------|-----------|--------|
| RF-01 | Conectar ao FreeSWITCH via ESL | Must | ✅ |
| RF-02 | Reconectar automaticamente com backoff | Must | ✅ |
| RF-03 | Escutar CHANNEL_CREATE, ANSWER, HANGUP, SOFIA_REGISTER, SOFIA_UNREGISTER | Must | ✅ |
| RF-04 | Mapear IP → ramal SIP no Redis | Must | ✅ |
| RF-05 | Implementar whisper mode (TTS no agente) | Should | ✅ |
| RF-06 | Tocar filler audio durante processamento | Should | ✅ |
| RF-07 | Detectar `*88` para linkage manual | Should | ✅ |
| RF-08 | 🆕 Manter conexão dedicada para `api`/`bgapi`, isolada do event stream | Must | ✅ 2026-07 (GAP-ESL-06) |
| RF-09 | 🆕 Fazer framing de evento por `Content-Length` | Must | ✅ 2026-07 (GAP-ESL-05) |
| RF-10 | 🆕 Disparar `uuid_audio_stream` via `bgapi` no `CHANNEL_ANSWER` | Must | ✅ (ADR-010) |
| RF-11 | 🆕 Criar a linha `Call` no `CHANNEL_ANSWER` e finalizá-la no `CHANNEL_HANGUP` | Must | ✅ |
| RF-12 | 🆕 Enfileirar `upload_recording_batch` com os chunks agrupados por canal | Must | ✅ |
| RF-13 | 🆕 Logar e seguir quando um handler lançar exceção | Must | ✅ |

## Requisitos Não-Funcionais

| ID | Requisito | Status |
|----|-----------|--------|
| RNF-01 | Conexão ociosa não deve ser derrubada por timeout curto | ✅ leitura com timeout de 300s |
| RNF-02 | Desconexão real deve ser detectada | ✅ por EOF (`read()` vazio) |
| RNF-03 | Um comando disparado de dentro de um handler não pode corromper o event stream | ✅ socket separado + `_cmd_lock` |
| RNF-04 | Eventos não podem ser perdidos durante reconexão | 🔴 **não atendido** — há janela sem consumo entre a queda e a reconexão |
| RNF-05 | Consumo de eventos com redundância | 🔴 **não atendido** — só `INSTANCE_ID == 1` (GAP-RE-01) |

## Rastreabilidade

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `src/telephony/esl_client.py` | `connect()`, `_connect_command()`, `_send_command()` | 🟢 |
| `src/telephony/esl_client.py` | `_read_events()` (framing por Content-Length) | 🟢 |
| `src/telephony/esl_client.py` | `_handle_channel_answer()`, `_start_audio_capture()` | 🟢 `tests/test_call_lifecycle.py` |
| `src/telephony/esl_client.py` | `_handle_channel_hangup()` | 🟢 `tests/test_call_lifecycle.py` |
| `src/telephony/esl_client.py` | `_handle_register()`, `_extract_ip()` | 🟢 `tests/test_telephony_matching.py` |
| `src/telephony/whisper_mode.py` | `whisper_to_agent()` | 🟢 |
| `src/telephony/filler_audio.py` | filler playback | 🟢 |

## Lacunas

| ID | Descrição |
|---|---|
| GAP-RE-01 | 🔴 Só uma instância consome ESL — sem failover para captura |
| GAP-RE-03 | 🔴 Chamada sem `tenant_id` é descartada em silêncio, sem métrica |
| GAP-PROV-01 | 🔴 `mod_xml_curl` não implementado — provisionamento dinâmico pendente |
| GAP-ESL-01 | 🟡 Sem heartbeat explícito |
| GAP-ESL-02 | 🔴 FreeSWITCH em `network_mode: host`, sem isolamento de rede |

## Dependência removida

`greenswitch==1.1.0` saiu do `requirements.txt` (GAP-18). O ESL sempre foi falado em socket
TCP bruto com `asyncio` — a dependência nunca foi de fato usada.
