# Audio, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar recepção de stream de áudio forked via WebSocket
  - Origem: `src/audio/ingestor.py:30-55`
  - Critério: chunks de áudio recebidos e publicados no Redis Stream
  - Confiança: 🟢

- [ ] T-02, Implementar detecção de canal (tx/rx)
  - Origem: `src/audio/ingestor.py:70-71` (🔴 stub)
  - Critério: canal "tx" para agente, "rx" para cliente baseado em metadados do FreeSWITCH
  - Confiança: 🔴

- [ ] T-03, Implementar registro de metadados do stream
  - Origem: `src/audio/ingestor.py:63-68`
  - Critério: metadados registrados no evento CHANNEL_ANSWER
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar recepção de stream de áudio
- [ ] TT-02, Testar publicação de chunk no Redis Stream
- [ ] TT-03, Testar detecção de canal (tx vs rx)
