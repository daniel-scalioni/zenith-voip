"""Estado idempotente de registros e chamadas de troncos ATA."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update

from src.database.models import ATATrunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegistrationEvent:
    status: str
    profile: str
    auth_username: str


def normalize_registration_event(event: dict) -> RegistrationEvent | None:
    status_by_event = {
        "sofia::register": "registered",
        "sofia::unregister": "unregistered",
        "sofia::expire": "unregistered",
        "SOFIA_REGISTER": "registered",
        "SOFIA_UNREGISTER": "unregistered",
    }
    event_type = event.get("Event-Subclass") or event.get("Event-Name")
    status = status_by_event.get(event_type)
    profile = event.get("profile-name") or event.get("Profile-Name") or event.get("variable_sofia_profile_name")
    username = (
        event.get("from-user")
        or event.get("from_user")
        or event.get("user")
        or event.get("username")
        or event.get("sip_auth_username")
        or event.get("variable_sip_auth_username")
        or event.get("Caller-Caller-ID-Number")
    )
    if status is None or not profile or not username:
        return None
    return RegistrationEvent(status=status, profile=str(profile), auth_username=str(username))


class TrunkStateService:
    ACTIVE_CALL_TTL_SECONDS = 86_400

    def __init__(self, repository, redis, resolver):
        self._repository = repository
        self._redis = redis
        self._resolver = resolver

    @staticmethod
    def _call_key(trunk_id: str) -> str:
        return f"zenith:trunk:active_calls:{trunk_id}"

    async def apply_registration_event(self, event: dict) -> bool:
        normalized = normalize_registration_event(event)
        if normalized is None:
            return False
        trunk_id = await self._resolver.resolve(normalized.profile, normalized.auth_username)
        if trunk_id is None:
            return False
        await self._repository.set_registration_status(trunk_id, normalized.status)
        return True

    async def track_call(self, trunk_id: str, call_uuid: str, *, active: bool) -> int:
        if not trunk_id or not call_uuid:
            return 0
        key = self._call_key(trunk_id)
        if active:
            await self._redis.sadd(key, call_uuid)
        else:
            await self._redis.srem(key, call_uuid)
        await self._redis.expire(key, self.ACTIVE_CALL_TTL_SECONDS)
        return max(0, int(await self._redis.scard(key)))

    async def active_calls(self, trunk_id: str) -> int:
        return max(0, int(await self._redis.scard(self._call_key(trunk_id))))

    async def reconcile(self, esl) -> dict[str, int]:
        unknown = int(await self._repository.mark_registered_unknown())
        result = {"unknown": unknown, "registered": 0, "errors": 0}
        try:
            registrations = await esl.list_registrations()
        except Exception:
            logger.exception("trunk_registration_reconciliation_unavailable")
            result["errors"] = 1
            return result
        for registration in registrations:
            try:
                trunk_id = await self._resolver.resolve(
                    registration.get("profile"), registration.get("auth_username")
                )
                if trunk_id is None:
                    result["errors"] += 1
                    continue
                await self._repository.set_registration_status(trunk_id, "registered")
                result["registered"] += 1
            except Exception:
                logger.exception("trunk_registration_reconciliation_row_failed")
                result["errors"] += 1
        await self._reconcile_active_calls(esl, result)
        return result

    async def _reconcile_active_calls(self, esl, result: dict[str, int]) -> None:
        list_channels = getattr(esl, "list_trunk_channels", None)
        list_trunks = getattr(self._repository, "list_enabled_ids", None)
        if not callable(list_channels) or not callable(list_trunks):
            return
        try:
            channels = await list_channels()
            trunk_ids = await list_trunks()
            if not isinstance(channels, list) or not isinstance(trunk_ids, list):
                return
            observed: dict[str, set[str]] = {}
            for channel in channels:
                trunk_id = channel.get("trunk_id")
                call_uuid = channel.get("call_uuid")
                if trunk_id and call_uuid:
                    observed.setdefault(str(trunk_id), set()).add(str(call_uuid))
            for trunk_id in trunk_ids:
                key = self._call_key(str(trunk_id))
                current = await self._redis.smembers(key)
                current_values = {
                    item.decode() if isinstance(item, bytes) else str(item) for item in current
                }
                expected = observed.get(str(trunk_id), set())
                for orphan in current_values - expected:
                    await self._redis.srem(key, orphan)
                for active in expected - current_values:
                    await self._redis.sadd(key, active)
                await self._redis.expire(key, self.ACTIVE_CALL_TTL_SECONDS)
        except Exception:
            logger.exception("trunk_active_call_reconciliation_failed")
            result["errors"] += 1


class TrunkStateRepository:
    def __init__(self, session):
        self._session = session

    async def mark_registered_unknown(self) -> int:
        result = await self._session.execute(
            update(ATATrunk)
            .where(ATATrunk.registration_status == "registered")
            .values(registration_status="unknown")
        )
        await self._session.commit()
        return int(result.rowcount or 0)

    async def set_registration_status(self, trunk_id: str, status: str) -> None:
        now = datetime.now(timezone.utc)
        values = {"registration_status": status}
        if status == "registered":
            values["last_registered_at"] = now
        elif status == "unregistered":
            values["last_unregistered_at"] = now
        await self._session.execute(
            update(ATATrunk).where(ATATrunk.id == trunk_id).values(**values)
        )
        await self._session.commit()

    async def list_enabled_ids(self) -> list[str]:
        result = await self._session.execute(
            select(ATATrunk.id).where(ATATrunk.enabled.is_(True))
        )
        return [str(item) for item in result.scalars().all()]


class TrunkIdentityResolver:
    def __init__(self, session):
        self._session = session

    async def resolve(self, profile: str | None, auth_username: str | None):
        if not profile or not auth_username:
            return None
        result = await self._session.execute(
            select(ATATrunk.id).where(
                ATATrunk.sip_profile == profile,
                ATATrunk.auth_username == auth_username,
                ATATrunk.enabled.is_(True),
            )
        )
        return result.scalar_one_or_none()
