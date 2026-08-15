import json
import os
from datetime import datetime, timedelta, timezone

import pytest
import asyncio

from src.audio.recording_lifecycle import acquire_lease, release_lease
from src.workers import audio_cleanup
from src.workers.recording_consumers import mark_consumed


@pytest.mark.asyncio
async def test_cleanup_removes_consumed_finals_before_ttl(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    for name in ("tx.wav", "rx.wav", "tx.raw", "rx.raw"):
        (call_dir / name).write_bytes(b"audio")
    mark_consumed(call_dir, "smb")
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup.settings, "AUDIO_RETENTION_DAYS", 90)
    monkeypatch.setattr(audio_cleanup.settings, "RECORDING_REQUIRED_CONSUMERS", ["smb"])

    # Act
    result = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Assert
    assert result["deleted"] == 4
    assert not (call_dir / "tx.wav").exists()
    assert (call_dir / ".consumed-smb").exists()


@pytest.mark.asyncio
async def test_cleanup_preserves_unconsumed_final_until_ttl_then_removes(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    audio = call_dir / "tx.wav"
    audio.write_bytes(b"audio")
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup.settings, "RECORDING_REQUIRED_CONSUMERS", ["smb"])
    monkeypatch.setattr(audio_cleanup.settings, "AUDIO_RETENTION_DAYS", 90)

    # Act
    first = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")
    monkeypatch.setattr(audio_cleanup.settings, "AUDIO_RETENTION_DAYS", 0)
    second = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Assert
    assert first["deleted"] == 0
    assert second["deleted"] == 1
    assert not audio.exists()


@pytest.mark.asyncio
async def test_temporary_is_deleted_only_on_second_unchanged_round(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    temporary = call_dir / "tx.tmp.raw"
    temporary.write_bytes(b"partial")
    now = datetime(2026, 8, 14, tzinfo=timezone.utc)
    clock = {"value": now}
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup, "_utc_now", lambda: clock["value"])

    # Act
    first = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")
    clock["value"] += timedelta(seconds=899)
    early = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")
    clock["value"] += timedelta(seconds=1)
    second = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Assert
    assert first["temporary_candidates"] == 1
    assert early["deleted"] == 0
    assert second["deleted"] == 1
    assert not temporary.exists()


@pytest.mark.asyncio
async def test_changed_file_or_reappearing_lease_cancels_candidate(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    temporary = call_dir / "tx.tmp.wav"
    temporary.write_bytes(b"one")
    now = datetime(2026, 8, 14, tzinfo=timezone.utc)
    clock = {"value": now}
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup, "_utc_now", lambda: clock["value"])
    await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Act: alteração cancela a observação anterior.
    temporary.write_bytes(b"changed")
    clock["value"] += timedelta(seconds=900)
    await audio_cleanup.cleanup_tenant_bucket({}, "tenant")
    lease = acquire_lease(call_dir, "conversion", "call", now=clock["value"], ttl_seconds=2000)
    clock["value"] += timedelta(seconds=900)
    protected = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Assert
    assert temporary.exists()
    assert protected["deleted"] == 0
    release_lease(call_dir, "conversion", lease.owner)


@pytest.mark.asyncio
async def test_corrupt_marker_and_control_files_do_not_abort_or_get_deleted(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    (call_dir / ".cleanup-candidates.json").write_text("{bad")
    (call_dir / ".consumed-smb").write_text("{}")
    (call_dir / "stereo.wav.tmp").write_bytes(b"remote-owned")
    (call_dir / "rx.tmp.raw").write_bytes(b"partial")
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup.settings, "AUDIO_RETENTION_DAYS", 0)

    # Act
    result = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Assert
    assert result["status"] == "ok"
    assert (call_dir / ".consumed-smb").exists()
    assert (call_dir / "stereo.wav.tmp").exists()
    assert (call_dir / "rx.tmp.raw").exists()


def test_worker_settings_declares_unique_exclusive_cleanup_queue():
    # Arrange / Act / Assert
    assert audio_cleanup.WorkerSettings.queue_name == "zenith:audio-cleanup"
    cron_job = audio_cleanup.WorkerSettings.cron_jobs[0]
    assert cron_job.unique


@pytest.mark.asyncio
async def test_two_concurrent_second_rounds_delete_idempotently(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    (call_dir / "rx.tmp.raw").write_bytes(b"partial")
    now = datetime(2026, 8, 14, tzinfo=timezone.utc)
    clock = {"value": now}
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup, "_utc_now", lambda: clock["value"])
    await audio_cleanup.cleanup_tenant_bucket({}, "tenant")
    clock["value"] += timedelta(seconds=900)

    # Act
    first, second = await asyncio.gather(
        audio_cleanup.cleanup_tenant_bucket({}, "tenant"),
        audio_cleanup.cleanup_tenant_bucket({}, "tenant"),
    )

    # Assert
    assert first["status"] == second["status"] == "ok"
    assert first["deleted"] + second["deleted"] == 1
