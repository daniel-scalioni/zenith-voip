# Audio, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar recepção de stream de áudio forked via WebSocket
  - Origem: `src/audio/ingestor.py:30-55`
  - Critério: chunks de áudio recebidos e publicados no Redis Stream
  - Confiança: 🟢

- [x] T-02, Implementar de-interleaving estéreo PCM16 em canais tx/rx
  - Origem: `src/audio/ingestor.py::AudioIngestor._split_stereo_frame`
  - Critério: cada frame estéreo gera dois `AudioChunk` (tx/rx) corretamente de-interleados
  - Testes: `tests/test_audio_ingestor.py` (verde)
  - Confiança: 🟡 — implementação correta para o protocolo documentado do `mod_audio_fork`; convenção de qual canal é tx vs rx ainda não validada contra FreeSWITCH real (ver GAP-01/GAP-11 em `gaps.md`)

- [ ] T-03, Implementar registro de metadados do stream
  - Origem: `src/audio/ingestor.py:63-68`
  - Critério: metadados registrados no evento CHANNEL_ANSWER
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar recepção de stream de áudio
- [ ] TT-02, Testar publicação de chunk no Redis Stream
- [x] TT-03, Testar detecção de canal (tx vs rx) — `tests/test_audio_ingestor.py`
