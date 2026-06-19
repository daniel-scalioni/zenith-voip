# Módulo: events

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/events/redis_streams.py` | Event bus via Redis Streams | 38 |

## Fluxo de Controle

- `RedisEventBus` abstrai Redis Streams como pub/sub assíncrono
- `publish(stream, event)` → xadd com serialização automática de dicts para JSON
- `consume(stream, group, consumer)` → xreadgroup com blocking
- `ack(stream, group, msg_id)` → confirma consumo
- `create_group(stream, group)` → cria consumer group (mkstream=true)

## Constantes (config.py)

| Constante | Valor |
|-----------|-------|
| REDIS_STREAM_CALL_EVENTS | "call:events" |
| REDIS_STREAM_POST_CALL | "call:post" |
| REDIS_CONSUMER_GROUP | "zenith-workers" |
