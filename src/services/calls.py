from datetime import datetime, timezone
from src.database.database import get_tenant_db
from src.database.models import Call, CallDirection, CallStatus
from src.services.base import Repository


def _tenant_schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"


async def create_call_record(tenant_id: str, call_id: str, pbx_id: str, agent_extension: str) -> None:
    schema = _tenant_schema(tenant_id)
    async for session in get_tenant_db(schema):
        repo = Repository(session, Call)
        await repo.create(
            call_id=call_id,
            pbx_id=pbx_id or None,
            agent_sip_extension=agent_extension or None,
            direction=CallDirection.inbound,
            status=CallStatus.in_progress,
        )


async def finalize_call_record(tenant_id: str, call_id: str) -> None:
    schema = _tenant_schema(tenant_id)
    async for session in get_tenant_db(schema):
        repo = Repository(session, Call)
        matches = await repo.find_by(call_id=call_id)
        if not matches:
            return
        existing = matches[0]
        ended_at = datetime.now(timezone.utc)
        duration = (ended_at - existing.started_at).total_seconds() if existing.started_at else None
        await repo.update(
            existing.id,
            status=CallStatus.completed,
            ended_at=ended_at,
            duration_seconds=duration,
        )
