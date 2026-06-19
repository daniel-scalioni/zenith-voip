from prometheus_client import Counter, Gauge, Histogram, generate_latest
from fastapi import Response

tenant_schemas_active = Gauge(
    "tenant_schemas_active",
    "Number of active tenant schemas in PostgreSQL",
)

redis_stream_events_total = Counter(
    "redis_stream_events_total",
    "Total Redis Stream events published",
    ["stream", "tenant_id"],
)

redis_stream_events_per_second = Gauge(
    "redis_stream_events_per_second",
    "Redis Stream events per second",
    ["stream"],
)

sip_mappings_active = Gauge(
    "sip_mappings_active",
    "Number of active SIP extension-to-IP mappings in Redis",
)

websocket_connections_active = Gauge(
    "websocket_connections_active",
    "Number of active WebSocket connections",
    ["tenant_id"],
)

db_pool_connections = Gauge(
    "db_pool_connections",
    "Database pool connection count",
)

multi_schema_query_duration = Histogram(
    "multi_schema_query_duration_seconds",
    "Duration of multi-schema database queries",
    ["schema"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
)


def set_active_tenant_schemas(count: int):
    tenant_schemas_active.set(count)


def inc_redis_stream_events(stream: str, tenant_id: str = ""):
    redis_stream_events_total.labels(stream=stream, tenant_id=tenant_id).inc()


def set_sip_mappings(count: int):
    sip_mappings_active.set(count)


def set_ws_connections(count: int, tenant_id: str = ""):
    websocket_connections_active.labels(tenant_id=tenant_id).set(count)


def set_db_pool_connections(count: int):
    db_pool_connections.set(count)


def observe_schema_query(schema: str, duration: float):
    multi_schema_query_duration.labels(schema=schema).observe(duration)


audio_cleanup_files_deleted = Counter(
    "audio_cleanup_files_deleted_total",
    "Total audio files deleted by cleanup worker",
    ["tenant_id"],
)

audio_cleanup_bytes_freed = Counter(
    "audio_cleanup_bytes_freed_total",
    "Total bytes freed by cleanup worker",
    ["tenant_id"],
)

audio_cleanup_duration = Histogram(
    "audio_cleanup_duration_seconds",
    "Duration of audio cleanup runs",
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

audio_cleanup_errors = Counter(
    "audio_cleanup_errors_total",
    "Total errors during audio cleanup",
    ["tenant_id"],
)


def record_cleanup_deleted(tenant_id: str, count: int, bytes_freed: int):
    audio_cleanup_files_deleted.labels(tenant_id=tenant_id).inc(count)
    audio_cleanup_bytes_freed.labels(tenant_id=tenant_id).inc(bytes_freed)


def record_cleanup_error(tenant_id: str):
    audio_cleanup_errors.labels(tenant_id=tenant_id).inc()


def observe_cleanup_duration(seconds: float):
    audio_cleanup_duration.observe(seconds)


async def metrics_endpoint():
    return Response(content=generate_latest(), media_type="text/plain")
