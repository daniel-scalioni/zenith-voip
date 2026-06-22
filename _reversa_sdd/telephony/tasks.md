# Telephony, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar cliente ESL com reconexão automática
  - Origem: `src/telephony/esl_client.py:30-88`
  - Critério: conexão estabelecida; reconexão com backoff de 2s em caso de queda
  - Confiança: 🟢

- [x] T-02, Implementar escuta de eventos FreeSWITCH
  - Origem: `src/telephony/esl_client.py` (`_process_event`, `_handle_channel_answer`, `_handle_channel_hangup`)
  - Critério: eventos CHANNEL_CREATE, ANSWER, HANGUP processados
  - Confiança: 🟢

- [x] T-07, Implementar ciclo de vida da `Call` no banco (answer cria, hangup finaliza) e disparo do flush/upload da gravação no hangup
  - Origem: `src/telephony/esl_client.py::_handle_channel_answer/_handle_channel_hangup`, `src/services/calls.py`, `src/workers/audio_uploader.py::enqueue_recording_upload`
  - Critério: `CHANNEL_ANSWER` cria `Call` (status=in_progress); `CHANNEL_HANGUP` finaliza (status=completed, ended_at, duration_seconds) e enfileira upload com os buffers acumulados
  - Testes: `tests/test_call_lifecycle.py` (verde)
  - Confiança: 🟡 — lógica testada via mocks; ainda não validada contra Postgres/Redis reais (ver Fase 4 do plano de MVP)

- [ ] T-03, Implementar mapeamento SIP → IP no Redis
  - Origem: `src/telephony/esl_client.py:179-184`
  - Critério: mapeamento bidirecional com TTL 3600s
  - Confiança: 🟢

- [ ] T-04, Implementar whisper mode
  - Origem: `src/telephony/whisper_mode.py:15-30`
  - Critério: TTS enviado para canal do agente durante chamada
  - Confiança: 🟢

- [ ] T-05, Implementar filler audio
  - Origem: `src/telephony/filler_audio.py:10-25`
  - Critério: áudio de preenchimento tocado para cliente
  - Confiança: 🟢

- [ ] T-06, Implementar detecção de *88 para linkage
  - Origem: `src/telephony/esl_client.py:136-137`
  - Critério: *88 dispara criação de sessão "awaiting_linkage"
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar conexão ESL
- [ ] TT-02, Testar reconexão automática
- [ ] TT-03, Testar mapeamento SIP→IP
- [ ] TT-04, Testar whisper mode
