from datetime import datetime, timezone
from src.database.database import get_tenant_db
from src.database.models import Call, CallDirection, CallStatus
from src.services.base import Repository


NORMAL_HANGUP_CAUSES = {"NORMAL_CLEARING", "NORMAL_UNSPECIFIED"}


def _tenant_schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"


async def create_call_record(
    tenant_id: str,
    call_id: str,
    pbx_id: str,
    agent_extension: str,
    caller_number: str | None = None,
    callee_number: str | None = None,
) -> None:
    schema = _tenant_schema(tenant_id)
    async for session in get_tenant_db(schema):
        repo = Repository(session, Call)
        await repo.create(
            call_id=call_id,
            pbx_id=pbx_id or None,
            agent_sip_extension=agent_extension or None,
            caller_number=caller_number or None,
            callee_number=callee_number or None,
            direction=CallDirection.inbound,
            status=CallStatus.in_progress,
        )


async def create_ringing_call_record(
    tenant_id: str,
    call_id: str,
    pbx_id: str,
    agent_extension: str,
    caller_number: str | None = None,
    callee_number: str | None = None,
) -> None:
    schema = _tenant_schema(tenant_id)
    async for session in get_tenant_db(schema):
        repo = Repository(session, Call)
        await repo.create(
            call_id=call_id,
            pbx_id=pbx_id or None,
            agent_sip_extension=agent_extension or None,
            caller_number=caller_number or None,
            callee_number=callee_number or None,
            direction=CallDirection.inbound,
            status=CallStatus.ringing,
        )


async def mark_call_in_progress(tenant_id: str, call_id: str) -> bool:
    """Promove a linha `ringing` criada no CHANNEL_CREATE para `in_progress`.
    Retorna False se nenhuma linha existir (tenant não resolvido no CREATE) —
    o chamador cai de volta para `create_call_record` nesse caso."""
    schema = _tenant_schema(tenant_id)
    async for session in get_tenant_db(schema):
        repo = Repository(session, Call)
        matches = await repo.find_by(call_id=call_id)
        if not matches:
            return False
        # Reseta started_at (nascido no CREATE, em ringing) para o momento do ANSWER — sem
        # isso, duration_seconds no hangup passaria a incluir o tempo de toque, mudando a
        # semântica de "duração da conversa" que o campo tinha antes deste fix.
        await repo.update(
            matches[0].id,
            status=CallStatus.in_progress,
            started_at=datetime.now(timezone.utc),
        )
        return True
    return False


async def finalize_call_record(tenant_id: str, call_id: str, hangup_cause: str | None = None) -> None:
    schema = _tenant_schema(tenant_id)
    async for session in get_tenant_db(schema):
        repo = Repository(session, Call)
        matches = await repo.find_by(call_id=call_id)
        if not matches:
            return
        existing = matches[0]
        ended_at = datetime.now(timezone.utc)
        duration = (ended_at - existing.started_at).total_seconds() if existing.started_at else None
        status = CallStatus.completed if hangup_cause in NORMAL_HANGUP_CAUSES else CallStatus.failed
        await repo.update(
            existing.id,
            status=status,
            ended_at=ended_at,
            duration_seconds=duration,
        )
