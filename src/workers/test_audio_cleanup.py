import json
from datetime import datetime, timedelta, timezone

import pytest
from arq.constants import default_queue_name

from src.workers import audio_cleanup


@pytest.mark.asyncio
async def test_cleanup_skips_call_directory_with_valid_lease(tmp_path, monkeypatch):
    # Arrange
    tenant_dir = tmp_path / "tenant"
    call_dir = tenant_dir / "call"
    call_dir.mkdir(parents=True)
    audio = call_dir / "tx.mp3"
    audio.write_bytes(b"audio")
    lease = call_dir / ".smb-processing"
    lease.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    old = (datetime.now(timezone.utc) - timedelta(days=1)).timestamp()
    audio.touch()
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup.settings, "AUDIO_RETENTION_DAYS", 0)

    # Act
    result = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Assert
    assert result["deleted"] == 0
    assert audio.exists()


@pytest.mark.asyncio
async def test_cleanup_treats_expired_or_corrupt_lease_as_inactive(tmp_path, monkeypatch):
    # Arrange
    tenant_dir = tmp_path / "tenant"
    expired_dir = tenant_dir / "expired"
    corrupt_dir = tenant_dir / "corrupt"
    expired_dir.mkdir(parents=True)
    corrupt_dir.mkdir()
    (expired_dir / "tx.mp3").write_bytes(b"audio")
    (corrupt_dir / "tx.mp3").write_bytes(b"audio")
    (expired_dir / ".smb-processing").write_text(
        json.dumps(
            {
                "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                "expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    (corrupt_dir / ".smb-processing").write_text("{bad", encoding="utf-8")
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup.settings, "AUDIO_RETENTION_DAYS", 0)

    # Act
    result = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Assert
    assert result["deleted"] >= 2
    assert not (expired_dir / "tx.mp3").exists()
    assert not (corrupt_dir / "tx.mp3").exists()


def test_worker_settings_declares_exclusive_cleanup_queue():
    # Arrange
    worker_settings = audio_cleanup.WorkerSettings

    # Act
    queue_name = getattr(worker_settings, "queue_name", None)

    # Assert
    assert queue_name == "zenith:audio-cleanup"
