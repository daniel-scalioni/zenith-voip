# Event Bus, Design

**Interface:** `publish(stream, event) → msg_id`, `consume(stream, group, consumer, count, block) → list[tuple]`, `ack(stream, group, msg_id) → None`
**Origem:** `src/events/redis_streams.py:10-38` 🟢
