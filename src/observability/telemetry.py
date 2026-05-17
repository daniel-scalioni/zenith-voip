from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Response
from src.config import settings

tracer = trace.get_tracer(__name__)

stt_latency = Histogram(
    "stt_latency_ms",
    "STT latency in milliseconds",
    ["provider"],
    buckets=[50, 100, 200, 300, 500, 1000, 2000],
)

stt_fallback_counter = Counter(
    "stt_fallback_total",
    "Total number of STT fallback activations",
    ["from_provider", "to_provider"],
)

llm_latency = Histogram(
    "llm_inference_latency_ms",
    "LLM inference latency in milliseconds",
    ["model"],
    buckets=[100, 200, 500, 1000, 2000, 5000],
)

call_active_gauge = Gauge(
    "calls_active",
    "Number of currently active calls",
)

call_duration = Histogram(
    "call_duration_seconds",
    "Call duration in seconds",
    buckets=[30, 60, 120, 300, 600, 1800],
)

consensus_decisions = Counter(
    "consensus_decisions_total",
    "Total consensus decisions",
    ["decision"],
)


def setup_telemetry(app):
    provider = TracerProvider()
    processor = BatchSpanProcessor(OTLPSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type="text/plain")


def record_stt_latency(provider: str, latency_ms: float):
    stt_latency.labels(provider=provider).observe(latency_ms)


def record_stt_fallback(from_provider: str, to_provider: str):
    stt_fallback_counter.labels(from_provider=from_provider, to_provider=to_provider).inc()


def record_llm_latency(model: str, latency_ms: float):
    llm_latency.labels(model=model).observe(latency_ms)


def set_active_calls(count: int):
    call_active_gauge.set(count)


def record_call_duration(seconds: float):
    call_duration.observe(seconds)


def record_consensus_decision(decision: str):
    consensus_decisions.labels(decision=decision).inc()
