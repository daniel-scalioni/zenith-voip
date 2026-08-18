import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.audio import recording_lifecycle as lifecycle


def test_lease_roundtrip_validates_owner_expiry_and_release(tmp_path):
    # Arrange
    now = datetime(2026, 8, 14, tzinfo=timezone.utc)

    # Act
    lease = lifecycle.acquire_lease(tmp_path, "capture", "call-1", now=now)

    # Assert
    assert lease.owner
    assert lifecycle.has_valid_lease(tmp_path, now=now + timedelta(seconds=119))
    assert not lifecycle.has_valid_lease(tmp_path, now=now + timedelta(seconds=121))
    assert not lifecycle.release_lease(tmp_path, "capture", "wrong-owner")
    assert lifecycle.release_lease(tmp_path, "capture", lease.owner)
    assert not lifecycle.release_lease(tmp_path, "capture", lease.owner)


def test_lease_rejects_unknown_stage_and_corrupt_json(tmp_path):
    # Arrange
    (tmp_path / ".capture-processing").write_text("{bad", encoding="utf-8")

    # Act / Assert
    assert not lifecycle.has_valid_lease(tmp_path)
    with pytest.raises(ValueError):
        lifecycle.acquire_lease(tmp_path, "unknown", "call")


def test_lease_rejects_stage_mismatch_and_non_uuid_owner(tmp_path):
    # Arrange
    path = tmp_path / ".capture-processing"
    path.write_text(json.dumps({
        "version": 1,
        "stage": "smb",
        "call_id": "call",
        "owner": "not-a-uuid",
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(),
    }))

    # Act / Assert
    assert not lifecycle.has_valid_lease(tmp_path)


def test_renew_requires_owner_and_writes_valid_versioned_json(tmp_path):
    # Arrange
    lease = lifecycle.acquire_lease(tmp_path, "conversion", "call")

    # Act
    assert not lifecycle.renew_lease(tmp_path, "conversion", "other")
    assert lifecycle.renew_lease(tmp_path, "conversion", lease.owner)
    payload = json.loads((tmp_path / ".conversion-processing").read_text())

    # Assert
    assert payload["version"] == 1
    assert payload["owner"] == lease.owner


def test_lease_excludes_different_owner_across_stages_and_allows_same_owner(tmp_path):
    # Arrange
    capture = lifecycle.acquire_lease(tmp_path, "capture", "call")

    # Act / Assert
    with pytest.raises(lifecycle.LeaseBusyError):
        lifecycle.acquire_lease(tmp_path, "smb", "call")

    nested = lifecycle.acquire_lease(
        tmp_path,
        "conversion",
        "call",
        owner=capture.owner,
    )
    assert nested.owner == capture.owner
    assert lifecycle.release_lease(tmp_path, "conversion", capture.owner)
    assert lifecycle.release_lease(tmp_path, "capture", capture.owner)


@pytest.mark.asyncio
async def test_heartbeat_stops_when_renewal_fails(tmp_path, monkeypatch):
    # Arrange
    lease = lifecycle.acquire_lease(tmp_path, "smb", "call")
    calls = 0

    def fail(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return False

    monkeypatch.setattr(lifecycle, "renew_lease", fail)

    # Act
    healthy = await lifecycle.heartbeat_lease(tmp_path, "smb", lease.owner, interval=0)

    # Assert
    assert not healthy
    assert calls == 1
