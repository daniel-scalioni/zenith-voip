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

trunk_active_calls = Gauge(
    "trunk_active_calls",
    "Quantidade agregada de chamadas ativas em troncos ATA",
    ["profile"],
)

trunk_directory_lookups_total = Counter(
    "trunk_directory_lookups_total",
    "Total de consultas ao diretório de troncos ATA",
    ["result", "profile"],
)

trunk_reconciliation_total = Counter(
    "trunk_reconciliation_total",
    "Total de resultados de reconciliação de troncos ATA",
    ["result"],
)

trunk_registration_state = Gauge(
    "trunk_registration_state",
    "Quantidade agregada de troncos ATA por estado",
    ["profile", "state"],
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

smb_backup_success_total = Counter(
    "smb_backup_success_total",
    "Total successful SMB audio backups",
)

smb_backup_failed_total = Counter(
    "smb_backup_failed_total",
    "Total failed SMB audio backup attempts",
)

smb_backup_latency_seconds = Histogram(
    "smb_backup_latency_seconds",
    "SMB audio backup latency",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 20, 30],
)

smb_backup_queue_size = Gauge(
    "smb_backup_queue_size",
    "Number of calls pending SMB backup",
)

smb_conversion_pending = Gauge(
    "smb_conversion_pending",
    "Number of calls waiting for audio conversion",
)

recording_storage_used_bytes = Gauge(
    "recording_storage_used_bytes", "Bytes currently used in recording tmpfs"
)
recording_storage_total_bytes = Gauge(
    "recording_storage_total_bytes", "Total bytes available in recording tmpfs"
)
recording_reserved_bytes = Gauge(
    "recording_reserved_bytes", "Remaining bytes reserved for active recordings"
)
recording_degraded_mode = Gauge(
    "recording_degraded_mode", "Whether admission of new recordings is suspended"
)
recording_refused_total = Counter(
    "recording_refused_total", "Recordings refused by capacity admission"
)
recording_temp_candidates_total = Counter(
    "recording_temp_candidates_total", "Temporary files observed as cleanup candidates"
)
recording_temp_deleted_total = Counter(
    "recording_temp_deleted_total", "Orphan temporary files deleted after revalidation"
)
recording_lease_failures_total = Counter(
    "recording_lease_failures_total", "Recording lease acquisition or renewal failures", ["stage"]
)


def record_cleanup_deleted(tenant_id: str, count: int, bytes_freed: int):
    audio_cleanup_files_deleted.labels(tenant_id=tenant_id).inc(count)
    audio_cleanup_bytes_freed.labels(tenant_id=tenant_id).inc(bytes_freed)


def record_cleanup_error(tenant_id: str):
    audio_cleanup_errors.labels(tenant_id=tenant_id).inc()


def observe_cleanup_duration(seconds: float):
    audio_cleanup_duration.observe(seconds)


def record_smb_success():
    smb_backup_success_total.inc()


def record_smb_failure():
    smb_backup_failed_total.inc()


def observe_smb_latency(seconds: float):
    smb_backup_latency_seconds.observe(seconds)


def set_smb_queue_size(count: int):
    smb_backup_queue_size.set(count)


def set_smb_conversion_pending(count: int):
    smb_conversion_pending.set(count)


def set_recording_capacity(*, used_bytes: int, reserved_bytes: int, total_bytes: int, degraded: bool):
    recording_storage_used_bytes.set(used_bytes)
    recording_reserved_bytes.set(reserved_bytes)
    recording_storage_total_bytes.set(total_bytes)
    recording_degraded_mode.set(int(degraded))


def record_recording_refused():
    recording_refused_total.inc()


def record_temporary_cleanup(*, candidates: int, deleted: int):
    recording_temp_candidates_total.inc(candidates)
    recording_temp_deleted_total.inc(deleted)


def record_lease_failure(stage: str):
    recording_lease_failures_total.labels(stage=stage).inc()


async def metrics_endpoint():
    return Response(content=generate_latest(), media_type="text/plain")
