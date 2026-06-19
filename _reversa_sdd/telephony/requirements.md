# Telephony — Integração FreeSWITCH

> Gerado pelo Writer — 2026-06-19

## Visão Geral

Integração com FreeSWITCH via Event Socket Layer (ESL): conexão, eventos de chamada, mapeamento SIP, whisper mode e filler audio.

## Responsabilidades

- Conectar ao FreeSWITCH via ESL com reconexão automática
- Escutar eventos de chamada (CHANNEL_CREATE, CHANNEL_ANSWER, CHANNEL_HANGUP, SOFIA_REGISTER, SOFIA_UNREGISTER)
- Mapear IP ↔ ramal SIP no Redis (TTL 1h)
- Implementar whisper mode (TTS no canal do agente)
- Tocar filler audio durante processamento
- Detectar código *88 para linkage manual

## Regras de Negócio

- Reconexão automática com backoff de 2s 🟢
- *88 é código de linkage manual 🟢
- SIP mappings expiram em 1h 🟢
- Widget tenta auto-reconnect a cada 3s 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF-01 | Conectar ao FreeSWITCH via ESL | Must |
| RF-02 | Reconectar automaticamente com backoff | Must |
| RF-03 | Escutar eventos CHANNEL_CREATE, ANSWER, HANGUP, SOFIA_REGISTER, SOFIA_UNREGISTER | Must |
| RF-04 | Mapear IP → ramal SIP no Redis | Must |
| RF-05 | Implementar whisper mode (TTS no agente) | Should |
| RF-06 | Tocar filler audio durante processamento | Should |
| RF-07 | Detectar *88 para linkage manual | Should |

## Rastreabilidade

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `src/telephony/esl_client.py` | `connect()`, `send_api()`, event handlers | 🟢 |
| `src/telephony/whisper_mode.py` | `whisper_to_agent()` | 🟢 |
| `src/telephony/filler_audio.py` | filler playback | 🟢 |
