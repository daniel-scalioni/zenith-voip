import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from arq.constants import default_queue_name

from src.audio.recording_lifecycle import acquire_lease, release_lease
from src.workers import audio_uploader


@pytest.mark.asyncio
async def test_convert_to_wav_uses_16000_and_publishes_atomically(tmp_path, monkeypatch):
    # Arrange
    raw = tmp_path / "tx.raw"
    raw.write_bytes(b"raw")
    captured = {}

    class Process:
        returncode = 0

        async def communicate(self):
            Path(captured["args"][-1]).write_bytes(b"wav")
            return b"", b""

    async def create_process(*args, **_kwargs):
        captured["args"] = args
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)

    # Act
    result = await audio_uploader._convert_to_wav(str(raw))

    # Assert
    assert result == str(tmp_path / "tx.wav")
    assert "16000" in captured["args"]
    assert "pcm_s16le" in captured["args"]
    assert raw.exists()
    assert not (tmp_path / "tx.tmp.wav").exists()


@pytest.mark.asyncio
async def test_convert_to_wav_preserves_raw_and_removes_partial_on_failure(tmp_path, monkeypatch):
    # Arrange
    raw = tmp_path / "rx.raw"
    raw.write_bytes(b"raw")

    class Process:
        returncode = 1

        async def communicate(self):
            (tmp_path / "rx.tmp.wav").write_bytes(b"partial")
            return b"", b"failure"

    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=Process()))

    # Act / Assert
    with pytest.raises(RuntimeError):
        await audio_uploader._convert_to_wav(str(raw))
    assert raw.exists()
    assert not (tmp_path / "rx.wav").exists()
    assert not (tmp_path / "rx.tmp.wav").exists()


@pytest.mark.asyncio
async def test_upload_batch_discovers_final_raws_and_preserves_them(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(audio_uploader.settings, "RECORDINGS_PATH", str(tmp_path))
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    (call_dir / "tx.raw").write_bytes(b"tx")
    (call_dir / "rx.tmp.raw").write_bytes(b"partial")

    async def convert(raw_path):
        output = raw_path.replace(".raw", ".wav")
        Path(output).write_bytes(b"wav")
        return output

    monkeypatch.setattr(audio_uploader, "_convert_to_wav", convert)

    # Act
    result = await audio_uploader.upload_recording_batch({}, "tenant", "call")

    # Assert
    assert result[0]["status"] == "uploaded"
    assert (call_dir / "tx.raw").exists()
    assert (call_dir / "tx.wav").exists()
    assert not (call_dir / "rx.wav").exists()


@pytest.mark.asyncio
async def test_duplicate_upload_observes_conversion_lease(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(audio_uploader.settings, "RECORDINGS_PATH", str(tmp_path))
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    lease = acquire_lease(call_dir, "conversion", "call")

    # Act
    result = await audio_uploader.upload_recording_batch({}, "tenant", "call")

    # Assert
    assert result == [{"status": "already_processing"}]
    release_lease(call_dir, "conversion", lease.owner)


@pytest.mark.asyncio
async def test_missing_raw_and_legacy_payload_are_safe_noop(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(audio_uploader.settings, "RECORDINGS_PATH", str(tmp_path))

    # Act
    missing = await audio_uploader.upload_recording_batch({}, "tenant", "missing")
    legacy = await audio_uploader.upload_recording_batch(
        {}, "tenant", "legacy", [{"channel": "tx", "data": b"bytes"}]
    )

    # Assert
    assert missing == []
    assert legacy == []


@pytest.mark.asyncio
async def test_conversion_aborts_when_lease_renewal_fails(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(audio_uploader.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(audio_uploader.settings, "RECORDING_LEASE_HEARTBEAT_SECONDS", 0)
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    (call_dir / "tx.raw").write_bytes(b"raw")
    monkeypatch.setattr(audio_uploader, "renew_lease", lambda *_args: False)

    async def slow_convert(_path):
        await asyncio.sleep(3600)

    monkeypatch.setattr(audio_uploader, "_convert_to_wav", slow_convert)

    # Act
    result = await audio_uploader.upload_recording_batch({}, "tenant", "call")

    # Assert
    assert result == [{"status": "lease_lost"}]
    assert not (call_dir / "tx.wav").exists()


@pytest.mark.asyncio
async def test_enqueue_uses_exclusive_queue_and_deterministic_job_id(monkeypatch):
    # Arrange
    captured = {}

    class Pool:
        async def enqueue_job(self, function, *args, **kwargs):
            captured.update(function=function, args=args, kwargs=kwargs)

    monkeypatch.setattr(audio_uploader, "_get_pool", AsyncMock(return_value=Pool()))

    # Act
    await audio_uploader.enqueue_recording_upload("tenant", "call")

    # Assert
    assert captured["function"] == "upload_recording_batch"
    assert captured["args"] == ("tenant", "call")
    assert captured["kwargs"]["_job_id"] == "recording-upload:tenant:call"


def test_worker_uses_exclusive_non_default_queue():
    # Arrange / Act / Assert
    assert audio_uploader.WorkerSettings.queue_name == "zenith:audio-upload"
    assert audio_uploader.WorkerSettings.queue_name != default_queue_name
