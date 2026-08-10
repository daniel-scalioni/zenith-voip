from unittest.mock import AsyncMock, MagicMock

import pytest


def _state():
    from src.telephony.trunk_state import TrunkStateService, normalize_registration_event

    return TrunkStateService, normalize_registration_event


class FakeRedisSet:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    async def sadd(self, key, value):
        before = len(self.values.setdefault(key, set()))
        self.values[key].add(value)
        return len(self.values[key]) - before

    async def srem(self, key, value):
        values = self.values.setdefault(key, set())
        existed = value in values
        values.discard(value)
        return int(existed)

    async def scard(self, key):
        return len(self.values.setdefault(key, set()))

    async def expire(self, key, seconds):
        self.expirations[key] = seconds
        return True

    async def smembers(self, key):
        return set(self.values.setdefault(key, set()))


@pytest.mark.parametrize(
    ("subclass", "expected"),
    [("sofia::register", "registered"), ("sofia::unregister", "unregistered"), ("sofia::expire", "unregistered")],
)
def test_normalize_registration_event_maps_custom_subclasses(subclass, expected):
    # Arrange
    _, normalize_registration_event = _state()
    event = {"Event-Subclass": subclass, "profile-name": "internal", "from-user": "ata-1"}

    # Act
    result = normalize_registration_event(event)

    # Assert
    assert result.status == expected
    assert result.profile == "internal"
    assert result.auth_username == "ata-1"


def test_normalize_expire_event_accepts_real_freeswitch_username_fields():
    # Arrange
    _, normalize_registration_event = _state()
    event = {
        "Event-Name": "CUSTOM",
        "Event-Subclass": "sofia::expire",
        "profile-name": "internal",
        "user": "spike012",
        "username": "spike012",
        "expires": "0",
    }

    # Act
    result = normalize_registration_event(event)

    # Assert
    assert result.status == "unregistered"
    assert result.profile == "internal"
    assert result.auth_username == "spike012"


def test_normalize_registration_event_returns_none_for_unrecognized_subclass():
    # Arrange
    _, normalize_registration_event = _state()
    event = {"Event-Subclass": "sofia::gateway_state", "profile-name": "internal", "from-user": "ata-1"}

    # Act
    result = normalize_registration_event(event)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_apply_registration_event_ignores_unrecognized_event():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    resolver = AsyncMock()
    service = TrunkStateService(repository, AsyncMock(), resolver)

    # Act
    applied = await service.apply_registration_event({"Event-Name": "CHANNEL_HANGUP"})

    # Assert
    assert applied is False
    resolver.resolve.assert_not_awaited()
    repository.set_registration_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_registration_event_ignores_unresolvable_identity():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    resolver = AsyncMock()
    resolver.resolve.return_value = None
    service = TrunkStateService(repository, AsyncMock(), resolver)
    event = {"Event-Subclass": "sofia::register", "profile-name": "internal", "from-user": "unknown-ata"}

    # Act
    applied = await service.apply_registration_event(event)

    # Assert
    assert applied is False
    repository.set_registration_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_registration_event_persists_resolved_status():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    resolver = AsyncMock()
    resolver.resolve.return_value = "trunk-1"
    service = TrunkStateService(repository, AsyncMock(), resolver)
    event = {"Event-Subclass": "sofia::register", "profile-name": "internal", "from-user": "ata-1"}

    # Act
    applied = await service.apply_registration_event(event)

    # Assert
    assert applied is True
    resolver.resolve.assert_awaited_once_with("internal", "ata-1")
    repository.set_registration_status.assert_awaited_once_with("trunk-1", "registered")


@pytest.mark.asyncio
async def test_active_calls_reads_redis_set_cardinality():
    # Arrange
    TrunkStateService, _ = _state()
    redis = FakeRedisSet()
    redis.values["zenith:trunk:active_calls:trunk-1"] = {"call-1", "call-2"}
    service = TrunkStateService(AsyncMock(), redis, AsyncMock())

    # Act
    result = await service.active_calls("trunk-1")

    # Assert
    assert result == 2


@pytest.mark.asyncio
async def test_track_call_uses_redis_set_for_idempotent_active_count():
    # Arrange
    TrunkStateService, _ = _state()
    redis = FakeRedisSet()
    service = TrunkStateService(AsyncMock(), redis, AsyncMock())

    # Act
    first = await service.track_call("trunk-1", "call-1", active=True)
    second = await service.track_call("trunk-1", "call-1", active=True)

    # Assert
    assert first == second == 1
    assert redis.values["zenith:trunk:active_calls:trunk-1"] == {"call-1"}
    assert redis.expirations["zenith:trunk:active_calls:trunk-1"] == 86_400


@pytest.mark.asyncio
async def test_track_unknown_hangup_never_returns_negative_count():
    # Arrange
    TrunkStateService, _ = _state()
    redis = FakeRedisSet()
    service = TrunkStateService(AsyncMock(), redis, AsyncMock())

    # Act
    result = await service.track_call("trunk-1", "missing-call", active=False)

    # Assert
    assert result == 0
    assert redis.values["zenith:trunk:active_calls:trunk-1"] == set()


@pytest.mark.asyncio
async def test_reconcile_marks_unknown_before_applying_observed_registrations():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    repository.mark_registered_unknown.return_value = 2
    resolver = AsyncMock()
    resolver.resolve.return_value = "trunk-1"
    esl = AsyncMock()
    esl.list_registrations.return_value = [{"profile": "internal", "auth_username": "ata-1"}]
    service = TrunkStateService(repository, AsyncMock(), resolver)

    # Act
    result = await service.reconcile(esl)

    # Assert
    repository.mark_registered_unknown.assert_awaited_once()
    repository.set_registration_status.assert_awaited_once_with("trunk-1", "registered")
    assert result == {"unknown": 2, "registered": 1, "errors": 0}


@pytest.mark.asyncio
async def test_reconcile_keeps_ambiguous_line_unknown_and_continues():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    repository.mark_registered_unknown.return_value = 1
    resolver = AsyncMock()
    resolver.resolve.side_effect = [None, "trunk-2"]
    esl = AsyncMock()
    esl.list_registrations.return_value = [
        {"profile": "internal", "auth_username": "ambiguous"},
        {"profile": "internal", "auth_username": "ata-2"},
    ]
    service = TrunkStateService(repository, AsyncMock(), resolver)

    # Act
    result = await service.reconcile(esl)

    # Assert
    repository.set_registration_status.assert_awaited_once_with("trunk-2", "registered")
    assert result["errors"] == 1


@pytest.mark.asyncio
async def test_reconcile_esl_failure_leaves_every_trunk_unknown_without_crashing():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    repository.mark_registered_unknown.return_value = 3
    esl = AsyncMock()
    esl.list_registrations.side_effect = ConnectionError("fixture-esl-offline")
    service = TrunkStateService(repository, FakeRedisSet(), AsyncMock())

    # Act
    result = await service.reconcile(esl)

    # Assert
    repository.mark_registered_unknown.assert_awaited_once()
    repository.set_registration_status.assert_not_awaited()
    assert result == {"unknown": 3, "registered": 0, "errors": 1}


@pytest.mark.asyncio
async def test_reconcile_counts_error_when_resolver_raises_mid_loop():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    repository.mark_registered_unknown.return_value = 1
    resolver = AsyncMock()
    resolver.resolve.side_effect = ConnectionError("fixture-db-offline")
    esl = AsyncMock()
    esl.list_registrations.return_value = [{"profile": "internal", "auth_username": "ata-1"}]
    service = TrunkStateService(repository, AsyncMock(), resolver)

    # Act
    result = await service.reconcile(esl)

    # Assert
    repository.set_registration_status.assert_not_awaited()
    assert result["errors"] == 1


@pytest.mark.asyncio
async def test_reconcile_skips_active_call_step_when_esl_or_repository_lack_channel_support():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    repository.mark_registered_unknown.return_value = 0
    del repository.list_enabled_ids
    redis = FakeRedisSet()
    esl = AsyncMock()
    esl.list_registrations.return_value = []
    del esl.list_trunk_channels
    service = TrunkStateService(repository, redis, AsyncMock())

    # Act
    result = await service.reconcile(esl)

    # Assert
    assert result["errors"] == 0
    assert redis.values == {}


@pytest.mark.asyncio
async def test_reconcile_adds_newly_observed_active_call_not_yet_tracked():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    repository.mark_registered_unknown.return_value = 0
    repository.list_enabled_ids.return_value = ["trunk-1"]
    redis = FakeRedisSet()
    esl = AsyncMock()
    esl.list_registrations.return_value = []
    esl.list_trunk_channels.return_value = [{"trunk_id": "trunk-1", "call_uuid": "call-new"}]
    service = TrunkStateService(repository, redis, AsyncMock())

    # Act
    await service.reconcile(esl)

    # Assert
    assert redis.values["zenith:trunk:active_calls:trunk-1"] == {"call-new"}


@pytest.mark.asyncio
async def test_reconcile_counts_error_when_active_call_reconciliation_raises():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    repository.mark_registered_unknown.return_value = 0
    repository.list_enabled_ids.side_effect = RuntimeError("fixture-db-error")
    redis = FakeRedisSet()
    esl = AsyncMock()
    esl.list_registrations.return_value = []
    esl.list_trunk_channels.return_value = []
    service = TrunkStateService(repository, redis, AsyncMock())

    # Act
    result = await service.reconcile(esl)

    # Assert
    assert result["errors"] == 1


@pytest.mark.asyncio
async def test_reconcile_removes_orphan_call_uuids_and_keeps_observed_channels():
    # Arrange
    TrunkStateService, _ = _state()
    repository = AsyncMock()
    repository.mark_registered_unknown.return_value = 0
    repository.list_enabled_ids.return_value = ["trunk-1"]
    redis = FakeRedisSet()
    redis.values["zenith:trunk:active_calls:trunk-1"] = {"call-live", "call-orphan"}
    esl = AsyncMock()
    esl.list_registrations.return_value = []
    esl.list_trunk_channels.return_value = [{"trunk_id": "trunk-1", "call_uuid": "call-live"}]
    service = TrunkStateService(repository, redis, AsyncMock())

    # Act
    await service.reconcile(esl)

    # Assert
    assert redis.values["zenith:trunk:active_calls:trunk-1"] == {"call-live"}


def _session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


def _query_result(scalar=None, scalars=()):
    result = MagicMock()
    result.rowcount = scalar
    result.scalar_one_or_none.return_value = scalar
    result.scalars.return_value.all.return_value = list(scalars)
    return result


@pytest.mark.asyncio
async def test_trunk_state_repository_marks_registered_rows_unknown():
    # Arrange
    from src.telephony.trunk_state import TrunkStateRepository

    session = _session()
    session.execute.return_value = _query_result(scalar=3)
    repository = TrunkStateRepository(session)

    # Act
    updated = await repository.mark_registered_unknown()

    # Assert
    assert updated == 3
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_trunk_state_repository_sets_registered_timestamp():
    # Arrange
    from src.telephony.trunk_state import TrunkStateRepository

    session = _session()
    repository = TrunkStateRepository(session)

    # Act
    await repository.set_registration_status("trunk-1", "registered")

    # Assert
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    statement = session.execute.await_args.args[0]
    params = statement.compile().params
    assert "last_registered_at" in params
    assert "last_unregistered_at" not in params


@pytest.mark.asyncio
async def test_trunk_state_repository_sets_unregistered_timestamp():
    # Arrange
    from src.telephony.trunk_state import TrunkStateRepository

    session = _session()
    repository = TrunkStateRepository(session)

    # Act
    await repository.set_registration_status("trunk-1", "unregistered")

    # Assert
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    statement = session.execute.await_args.args[0]
    params = statement.compile().params
    assert "last_unregistered_at" in params
    assert "last_registered_at" not in params


@pytest.mark.asyncio
async def test_trunk_state_repository_lists_only_enabled_ids():
    # Arrange
    from src.telephony.trunk_state import TrunkStateRepository

    session = _session()
    session.execute.return_value = _query_result(scalars=("trunk-1", "trunk-2"))
    repository = TrunkStateRepository(session)

    # Act
    ids = await repository.list_enabled_ids()

    # Assert
    assert ids == ["trunk-1", "trunk-2"]


@pytest.mark.asyncio
async def test_trunk_identity_resolver_returns_none_without_profile_or_username():
    # Arrange
    from src.telephony.trunk_state import TrunkIdentityResolver

    resolver = TrunkIdentityResolver(_session())

    # Act
    result = await resolver.resolve(None, "ata-1")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_trunk_identity_resolver_resolves_enabled_trunk_id():
    # Arrange
    from src.telephony.trunk_state import TrunkIdentityResolver

    session = _session()
    session.execute.return_value = _query_result(scalar="trunk-1")
    resolver = TrunkIdentityResolver(session)

    # Act
    result = await resolver.resolve("internal-7060", "ata-1")

    # Assert
    assert result == "trunk-1"
    session.execute.assert_awaited_once()
