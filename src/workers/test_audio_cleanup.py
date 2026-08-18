import json
import os
import shutil
import threading
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
async def test_cleanup_never_expires_wav_in_transcription_backlog(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    for name in ("tx.wav", "rx.wav"):
        (call_dir / name).write_bytes(b"audio")
    mark_consumed(call_dir, "smb")
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup.settings, "RECORDING_REQUIRED_CONSUMERS", ["smb", "transcription"])
    monkeypatch.setattr(audio_cleanup.settings, "AUDIO_RETENTION_DAYS", 0)

    # Act
    pending = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")
    mark_consumed(call_dir, "transcription")
    consumed = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Assert
    assert pending["deleted"] == 0
    assert consumed["deleted"] == 2


@pytest.mark.asyncio
async def test_cleanup_sheds_expired_transcription_backlog_under_capacity_pressure(
    tmp_path, monkeypatch
):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    for name in ("tx.wav", "rx.wav"):
        (call_dir / name).write_bytes(b"audio")
    mark_consumed(call_dir, "smb")
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup.settings, "RECORDING_REQUIRED_CONSUMERS", ["smb", "transcription"])
    monkeypatch.setattr(audio_cleanup.settings, "AUDIO_RETENTION_DAYS", 0)
    monkeypatch.setattr(
        audio_cleanup.shutil,
        "disk_usage",
        lambda _path: shutil._ntuple_diskusage(total=100, used=90, free=10),
    )
    dropped = []
    monkeypatch.setattr(
        audio_cleanup, "record_transcript_backlog_dropped", lambda tenant_id: dropped.append(tenant_id)
    )

    # Act
    result = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Assert
    assert result["deleted"] == 2
    assert dropped == ["tenant"]


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
    marker_during_lease = call_dir / ".cleanup-candidates.json"
    release_lease(call_dir, "conversion", lease.owner)
    after_release_at = clock["value"]
    after_release = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")
    marker_after_release = json.loads(marker_during_lease.read_text())
    clock["value"] += timedelta(seconds=900)
    after_second_observation = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")

    # Assert
    assert protected["deleted"] == 0
    assert after_release["deleted"] == 0
    assert marker_after_release["tx.tmp.wav"]["first_seen"] == after_release_at.isoformat()
    assert after_second_observation["deleted"] == 1
    assert not temporary.exists()


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


@pytest.mark.asyncio
async def test_structurally_invalid_candidate_is_rebuilt_without_aborting_bucket(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    temporary = call_dir / "tx.tmp.raw"
    temporary.write_bytes(b"partial")
    marker = call_dir / ".cleanup-candidates.json"
    marker.write_text(json.dumps({temporary.name: None}), encoding="utf-8")
    now = datetime(2026, 8, 14, tzinfo=timezone.utc)
    monkeypatch.setattr(audio_cleanup.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_cleanup, "_utc_now", lambda: now)

    # Act
    result = await audio_cleanup.cleanup_tenant_bucket({}, "tenant")
    rebuilt = json.loads(marker.read_text())

    # Assert
    assert result["status"] == "ok"
    assert temporary.exists()
    assert rebuilt[temporary.name]["first_seen"] == now.isoformat()


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
    original_delete = audio_cleanup._delete
    first_delete_entered = threading.Event()
    allow_first_delete = threading.Event()
    counter_lock = threading.Lock()
    delete_calls = 0

    def block_first_delete(path):
        nonlocal delete_calls
        with counter_lock:
            delete_calls += 1
            call_number = delete_calls
        if call_number == 1:
            first_delete_entered.set()
            assert allow_first_delete.wait(timeout=2)
        return original_delete(path)

    monkeypatch.setattr(audio_cleanup, "_delete", block_first_delete)

    # Act
    first_task = asyncio.create_task(asyncio.to_thread(
        audio_cleanup._cleanup_call_directory, call_dir, 0, clock["value"],
    ))
    assert await asyncio.to_thread(first_delete_entered.wait, 1)
    second_task = asyncio.create_task(asyncio.to_thread(
        audio_cleanup._cleanup_call_directory, call_dir, 0, clock["value"],
    ))
    await asyncio.sleep(0.05)
    second_was_serialized = not second_task.done()
    allow_first_delete.set()
    first, second = await asyncio.gather(first_task, second_task)

    # Assert
    assert second_was_serialized
    assert first[0] + second[0] == 1


@pytest.mark.asyncio
async def test_lease_acquisition_waits_for_cleanup_critical_section(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    temporary = call_dir / "rx.tmp.raw"
    temporary.write_bytes(b"partial")
    now = datetime(2026, 8, 14, tzinfo=timezone.utc)
    audio_cleanup._cleanup_call_directory(call_dir, 0, now)
    original_delete = audio_cleanup._delete
    delete_entered = threading.Event()
    allow_delete = threading.Event()
    acquire_started = threading.Event()

    def blocked_delete(path):
        delete_entered.set()
        assert allow_delete.wait(timeout=2)
        return original_delete(path)

    def acquire_capture_lease():
        acquire_started.set()
        return acquire_lease(call_dir, "capture", "call", now=now + timedelta(seconds=901))

    monkeypatch.setattr(audio_cleanup, "_delete", blocked_delete)

    # Act
    cleanup_task = asyncio.create_task(asyncio.to_thread(
        audio_cleanup._cleanup_call_directory,
        call_dir,
        0,
        now + timedelta(seconds=901),
    ))
    assert await asyncio.to_thread(delete_entered.wait, 1)
    lease_task = asyncio.create_task(asyncio.to_thread(acquire_capture_lease))
    assert await asyncio.to_thread(acquire_started.wait, 1)
    await asyncio.sleep(0.05)
    lease_was_serialized = not lease_task.done()
    allow_delete.set()
    cleanup_result, lease = await asyncio.gather(cleanup_task, lease_task)

    # Assert
    assert lease_was_serialized
    assert cleanup_result[0] == 1
    assert not temporary.exists()
    assert release_lease(call_dir, "capture", lease.owner)
