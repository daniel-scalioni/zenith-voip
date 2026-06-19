# Events, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Interface

| Símbolo | Assinatura | Retorno |
|---------|-----------|---------|
| `publish` | `(stream: str, event: dict)` | `str` (msg_id) |
| `consume` | `(stream: str, group: str, consumer: str, count: int, block: int)` | `list[tuple]` |
| `ack` | `(stream: str, group: str, msg_id: str)` | `None` |
| `create_group` | `(stream: str, group: str)` | `None` |

### Streams

| Stream | Grupo | Consumidores |
|--------|-------|-------------|
| `call:events` | zenith-workers | Workers STT, extração, IA, post-call |
| `call:post` | - | Eventos pós-chamada |

## Fluxo Principal

1. Produtor chama `publish("call:events", event)` — `src/events/redis_streams.py:10-18`
2. Consumidor chama `consume("call:events", "zenith-workers", "worker-1")` — `src/events/redis_streams.py:22-30`
3. Mensagem processada e acknowledged via `ack()` — `src/events/redis_streams.py:34-38`

## Riscos e Lacunas

- 🟡 Sem retry automático em caso de falha de processamento
- 🟡 Sem dead-letter queue para mensagens não processáveis
