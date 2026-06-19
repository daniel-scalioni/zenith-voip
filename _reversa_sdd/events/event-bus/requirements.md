# Event Bus (events/event-bus)

**Responsabilidades:** Publicar/consumir eventos via Redis Streams
**RF:** publish, consume, ack, create_group
**Streams:** call:events (grupo zenith-workers), call:post
**Origem:** `src/events/redis_streams.py`
