# Events, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar publish em Redis Stream
  - Origem: `src/events/redis_streams.py:10-18`
  - Critério: evento publicado, retorna msg_id
  - Confiança: 🟢

- [ ] T-02, Implementar consume com consumer group
  - Origem: `src/events/redis_streams.py:22-30`
  - Critério: mensagens consumidas do stream com grupo
  - Confiança: 🟢

- [ ] T-03, Implementar ack de mensagens
  - Origem: `src/events/redis_streams.py:34-38`
  - Critério: mensagem acknowledged após processamento
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar publish e consume de evento
- [ ] TT-02, Testar ack após consumo
- [ ] TT-03, Testar consumer group recovery
