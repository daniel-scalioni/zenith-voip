import asyncio
from pathlib import Path

import pytest
from arq.constants import default_queue_name

from src.workers import audio_cleanup, audio_uploader, smb_sync


@pytest.mark.asyncio
async def test_convert_to_mp3_publishes_atomically(tmp_path, monkeypatch):
    # Arrange
    raw = tmp_path / "tx.raw"
    raw.write_bytes(b"raw")
    replace_calls = []

    class Process:
        returncode = 0

        async def communicate(self):
            Path(self.output).write_bytes(b"mp3")
            return b"", b""

    async def create_process(*args, **_kwargs):
        process = Process()
        process.output = args[-1]
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    real_replace = audio_uploader.os.replace

    def track_replace(source, destination):
        replace_calls.append((source, destination))
        real_replace(source, destination)

    monkeypatch.setattr(audio_uploader.os, "replace", track_replace)

    # Act
    result = await audio_uploader._convert_to_mp3(str(raw))

    # Assert
    assert result == str(tmp_path / "tx.mp3")
    assert replace_calls == [(str(tmp_path / "tx.tmp.mp3"), str(tmp_path / "tx.mp3"))]
    assert raw.exists()


@pytest.mark.asyncio
async def test_convert_to_mp3_preserves_raw_and_no_final_on_failure(tmp_path, monkeypatch):
    # Arrange
    raw = tmp_path / "rx.raw"
    raw.write_bytes(b"raw")

    class Process:
        returncode = 1

        async def communicate(self):
            return b"", b"failure"

    async def create_process(*_args, **_kwargs):
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)

    # Act / Assert
    with pytest.raises(RuntimeError):
        await audio_uploader._convert_to_mp3(str(raw))
    assert raw.exists()
    assert not (tmp_path / "rx.mp3").exists()
    assert not (tmp_path / "rx.tmp.mp3").exists()


@pytest.mark.asyncio
async def test_upload_audio_chunk_removes_raw_only_after_conversion(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(audio_uploader.settings, "RECORDINGS_PATH", str(tmp_path))

    async def convert(raw_path):
        mp3_path = raw_path.replace(".raw", ".mp3")
        Path(mp3_path).write_bytes(b"mp3")
        return mp3_path

    monkeypatch.setattr(audio_uploader, "_convert_to_mp3", convert)

    # Act
    result = await audio_uploader.upload_audio_chunk(
        {}, "tenant", "call", "tx", b"raw"
    )

    # Assert
    assert result["status"] == "uploaded"
    assert Path(result["path"]).read_bytes() == b"mp3"
    assert not (tmp_path / "tenant" / "call" / "tx.raw").exists()


@pytest.mark.asyncio
async def test_upload_audio_chunk_preserves_raw_on_conversion_failure(
    tmp_path, monkeypatch
):
    # Arrange
    monkeypatch.setattr(audio_uploader.settings, "RECORDINGS_PATH", str(tmp_path))

    async def fail(_raw_path):
        raise RuntimeError("ffmpeg unavailable")

    monkeypatch.setattr(audio_uploader, "_convert_to_mp3", fail)

    # Act
    result = await audio_uploader.upload_audio_chunk(
        {}, "tenant", "call", "rx", b"raw"
    )

    # Assert
    assert result["status"] == "uploaded_raw_only"
    assert Path(result["path"]).read_bytes() == b"raw"


def test_worker_settings_declares_exclusive_upload_queue():
    # Arrange
    worker_settings = audio_uploader.WorkerSettings

    # Act
    queue_name = getattr(worker_settings, "queue_name", None)

    # Assert
    assert queue_name == "zenith:audio-upload"


@pytest.mark.asyncio
async def test_enqueue_recording_upload_publishes_to_exclusive_queue(monkeypatch):
    # Arrange
    captured = {}

    class FakePool:
        def __init__(self, pool_default_queue_name):
            self.default_queue_name = pool_default_queue_name

        async def enqueue_job(self, function, *_args, **kwargs):
            captured["function"] = function
            captured["queue"] = kwargs.get("_queue_name") or self.default_queue_name

    async def fake_create_pool(_settings=None, **kwargs):
        return FakePool(kwargs.get("default_queue_name", default_queue_name))

    monkeypatch.setattr(audio_uploader, "create_pool", fake_create_pool)
    monkeypatch.setattr(audio_uploader, "_pool", None)

    # Act
    await audio_uploader.enqueue_recording_upload(
        "tenant-1", "call-001", [{"channel": "tx", "data": b"\x00"}]
    )

    # Assert
    assert captured["function"] == "upload_recording_batch"
    assert captured["queue"] == "zenith:audio-upload"


def test_worker_queues_are_isolated_and_prevent_cross_consumption():
    # Arrange
    def effective_queue_name(worker_settings) -> str:
        return getattr(worker_settings, "queue_name", None) or default_queue_name

    # Act
    effective_queues = {
        effective_queue_name(audio_uploader.WorkerSettings),
        effective_queue_name(audio_cleanup.WorkerSettings),
        effective_queue_name(smb_sync.WorkerSettings),
    }
    upload_function_names = {fn.__name__ for fn in audio_uploader.WorkerSettings.functions}
    cleanup_function_names = {fn.__name__ for fn in audio_cleanup.WorkerSettings.functions}
    smb_function_names = {fn.__name__ for fn in smb_sync.WorkerSettings.functions}

    # Assert
    assert len(effective_queues) == 3
    assert default_queue_name not in effective_queues
    assert "upload_recording_batch" in upload_function_names
    assert "upload_recording_batch" not in cleanup_function_names
    assert "upload_recording_batch" not in smb_function_names
    assert "run_cleanup" in cleanup_function_names
    assert "run_cleanup" not in upload_function_names
    assert "run_cleanup" not in smb_function_names
    assert "run_smb_sync" in smb_function_names
    assert "run_smb_sync" not in upload_function_names
    assert "run_smb_sync" not in cleanup_function_names
