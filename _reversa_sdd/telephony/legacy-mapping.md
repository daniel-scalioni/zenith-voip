# Módulo: telephony

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/telephony/esl_client.py` | Cliente FreeSWITCH ESL (Event Socket Layer) | 206 |
| `src/telephony/filler_audio.py` | Áudio de preenchimento em chamadas | 20 |
| `src/telephony/whisper_mode.py` | Modo Whisper (TTS no canal do agente) | 24 |

## Fluxo de Controle

### esl_client.py — Core
- `ESLClient` gerencia conexão TCP com FreeSWITCH ESL
- `connect()` → autentica com password, subscribe em eventos JSON
- Eventos escutados: CHANNEL_CREATE, CHANNEL_ANSWER, CHANNEL_HANGUP, SOFIA_REGISTER, SOFIA_UNREGISTER
- `send_api(command)` → envia comando e aguarda resposta
- `send_bgapi(command)` → envia comando bgapi
- `start_event_listener()` → task asíncrona de event loop
- `_event_loop()` → loop de reconexão automática com backoff
- `_process_event()` → roteia eventos para handlers específicos

### Handlers de Eventos ESL
- `_handle_register()` → mapeia SIP user → IP no Redis (TTL 3600s)
- `_handle_unregister()` → remove mapeamento SIP do Redis
- `_handle_channel_create()` → detecta *88 para manual linkage
- `_handle_channel_answer()` → registra metadados no audio_ingestor

### Whisper Mode
- `WhisperMode.whisper_to_agent()` → sintetiza TTS e toca no canal do agente via uuid_play

### Filler Audio
- `FillerAudio.play_to_customer()` → toca áudio de espera no canal do cliente

## Algoritmos

**SIP IP Extraction**: Extrai IP do evento ESL de múltiplos campos (sip_network_ip, Caller-Network-Addr, sip_via_host, Caller-Source) com regex fallback.

**Reconexão Automática**: Em caso de erro de conexão, aguarda 2s e reconecta automaticamente.

## Mapeamentos Redis

| Chave | TTL | Descrição |
|-------|-----|-----------|
| zenith:sip:ip_to_extension:{ip} | 3600s | IP → ramal SIP |
| zenith:sip:extension_to_ip:{extension} | 3600s | Ramal SIP → IP |
| zenith:sip:extension_to_pbx:{extension} | - | Ramal → PBX (inserido externamente) |
| zenith:ws:agent_session:{agent_uuid} | 30-120s | Sessão WebSocket do agente |

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Reconexão automática com backoff de 2s | `esl_client.py:86-88` | 🟢 |
| *88 é código de linkage manual | `esl_client.py:136-137` | 🟢 |
| SIP mappings expiram em 1h | `esl_client.py:179-184` | 🟢 |
| Mapeamento UUID mantido em memória | `esl_client.py:20,57-66` | 🟢 |
