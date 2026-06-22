from sqlalchemy import Column, String, DateTime, Float, JSON, ForeignKey, Text, Enum as SAEnum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()

TenantBase = declarative_base()


class CallDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class CallStatus(str, enum.Enum):
    ringing = "ringing"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    schema_name = Column(String(64), unique=True, nullable=False)
    status = Column(String(32), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    pbxs = relationship("PBX", back_populates="tenant", cascade="all, delete-orphan")


class PBX(Base):
    __tablename__ = "pbxs"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    host = Column(String(128), nullable=False)
    port = Column(Integer, default=5060)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="pbxs")


class Call(TenantBase):
    __tablename__ = "calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(String(128), unique=True, nullable=False, index=True)
    agent_uuid = Column(String(128), nullable=True)
    customer_uuid = Column(String(128), nullable=True)
    pbx_id = Column(UUID(as_uuid=True), nullable=True)
    agent_sip_extension = Column(String(64), nullable=True)
    direction = Column(SAEnum(CallDirection), nullable=False)
    status = Column(SAEnum(CallStatus), default=CallStatus.in_progress)
    caller_number = Column(String(32), nullable=True)
    callee_number = Column(String(32), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    extra_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    transcripts = relationship("Transcript", back_populates="call", cascade="all, delete-orphan")
    insights = relationship("CallInsight", back_populates="call", cascade="all, delete-orphan")


class Transcript(TenantBase):
    __tablename__ = "transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(16), nullable=False)
    speaker = Column(String(64), nullable=True)
    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    is_final = Column(default=True)
    extra_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    call = relationship("Call", back_populates="transcripts")


class CallInsight(TenantBase):
    __tablename__ = "call_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    sentiment = Column(String(32), nullable=True)
    sentiment_score = Column(Float, nullable=True)
    entities = Column(JSONB, nullable=True)
    consensus_log = Column(JSONB, nullable=True)
    pop_checklist = Column(JSONB, nullable=True)
    anomaly_detected = Column(default=False)
    summary = Column(Text, nullable=True)
    raw_insight = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    call = relationship("Call", back_populates="insights")


class STTMetric(TenantBase):
    __tablename__ = "stt_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(String(128), nullable=True, index=True)
    provider = Column(String(32), nullable=False)
    latency_ms = Column(Float, nullable=False)
    chunk_duration_ms = Column(Float, nullable=True)
    success = Column(default=True)
    fallback_activated = Column(default=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
