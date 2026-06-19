# Events — Event Bus

> Gerado pelo Writer — 2026-06-19

## Visão Geral

Abstração sobre Redis Streams para publish/consume de eventos assíncronos entre componentes do sistema.

## Responsabilidades

- Publicar eventos em streams Redis
- Consumir eventos com consumer groups
- Gerenciar acknowledgment de mensagens

## Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF-01 | Publicar evento em stream Redis | Must |
| RF-02 | Consumir eventos de stream com consumer group | Must |
| RF-03 | Fazer ack de mensagens consumidas | Must |
| RF-04 | Criar consumer group se não existir | Must |

## Rastreabilidade

| Arquivo | Função | Cobertura |
|---------|--------|-----------|
| `src/events/redis_streams.py` | `publish()`, `consume()`, `ack()`, `create_group()` | 🟢 |
