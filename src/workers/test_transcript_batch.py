from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import asyncio
import json
import wave

import pytest

from src.workers import transcript_batch


def _wav_pair(directory: Path):
    directory.mkdir(parents=True)
    for channel in ("tx", "rx"):
        with wave.open(str(directory / f"{channel}.wav"), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(16_000)
            target.writeframes(b"\x00\x00" * 160)


def test_ready_call_requires_two_final_nonempty_wavs_without_temporary(tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    _wav_pair(call_dir)

    # Act / Assert
    assert transcript_batch.is_ready_call(call_dir)
    (call_dir / "rx.wav").write_bytes(b"")
    assert not transcript_batch.is_ready_call(call_dir)
    with wave.open(str(call_dir / "rx.wav"), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x00\x00" * 160)
    (call_dir / "tx.tmp.wav").write_bytes(b"partial")
    assert not transcript_batch.is_ready_call(call_dir)


@pytest.mark.parametrize(
    ("channels", "sample_width", "sample_rate"),
    [(2, 2, 16_000), (1, 2, 8_000), (1, 1, 16_000)],
)
def test_ready_call_rejects_wav_outside_pcm16_mono_16khz(
    tmp_path, channels, sample_width, sample_rate
):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    _wav_pair(call_dir)
    with wave.open(str(call_dir / "rx.wav"), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(sample_width)
        target.setframerate(sample_rate)
        target.writeframes(b"\x00" * sample_width * channels * 160)

    # Act / Assert
    assert not transcript_batch.is_ready_call(call_dir)


def test_normalize_segments_maps_speakers_offsets_and_discards_silence():
    # Arrange
    raw = [
        {"text": "  ", "start": 0.0, "end": 1.0, "confidence": 0.1},
        {"text": "Olá", "start": 0.25, "end": 1.5, "confidence": 1.4},
    ]

    # Act
    segments = transcript_batch.normalize_segments("tx", raw, chunk_offset=30.0, chunk_index=1)

    # Assert
    assert segments == [{
        "channel": "tx", "speaker": "atendente", "text": "Olá",
        "confidence": 1.0, "start_time": 30.25, "end_time": 31.5,
        "is_final": True, "extra_metadata": {"chunk_index": 1},
    }]


def test_render_markdown_interleaves_channels_and_formats_timestamps():
    # Arrange
    metadata = {
        "call_id": "call-1", "tenant_id": "tenant-a",
        "started_at": datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc),
        "caller_number": "1001", "callee_number": "2002",
    }
    segments = [
        {"speaker": "cliente", "text": "Oi", "start_time": 2.5, "end_time": 3.0, "confidence": 0.8},
        {"speaker": "atendente", "text": "Bom dia", "start_time": 0.0, "end_time": 1.2, "confidence": 0.9},
    ]

    # Act
    content = transcript_batch.render_markdown(metadata, segments)

    # Assert
    assert content.index("Bom dia") < content.index("Oi")
    assert "[00:00:00.000 → 00:00:01.200] **Atendente** (confidence: 0.90)" in content
    assert "[00:00:02.500 → 00:00:03.000] **Cliente** (confidence: 0.80)" in content


def test_remote_names_share_audio_base_and_md_extension():
    # Arrange
    metadata = {
        "started_at": datetime(2026, 8, 18, 12, 1, 2, tzinfo=timezone.utc),
        "call_id": "abcdef123", "caller_number": "1001", "callee_number": "2002",
    }

    # Act
    remote_dir, md_name, collision = transcript_batch.build_transcript_remote_names("tenant", metadata)

    # Assert
    assert remote_dir == "tenant/2026-08-18"
    assert md_name == "2026-08-18-12-01-02-abcdef-1001-2002.md"
    assert collision.endswith("-123.md")


def test_smb_transfer_log_owns_exact_collision_name(tmp_path):
    # Arrange
    log_path = tmp_path / "smb.json"
    log_path.write_text(json.dumps({"tenant/abcdef123": {
        "tenant_id": "tenant", "call_id": "abcdef123", "status": "done",
        "started_at": "2026-08-18T12:01:02+00:00",
        "remote_name": "2026-08-18-12-01-02-abcdef-1001-2002-123.wav",
    }}), encoding="utf-8")

    # Act
    reference = transcript_batch.load_smb_audio_reference(log_path, "tenant", "abcdef123")

    # Assert
    assert reference == {
        "remote_dir": "tenant/2026-08-18",
        "remote_wav_name": "2026-08-18-12-01-02-abcdef-1001-2002-123.wav",
        "remote_md_name": "2026-08-18-12-01-02-abcdef-1001-2002-123.md",
    }


@pytest.mark.parametrize("remote_name", ["../evil.wav", "..\\evil.wav", "evil.md", "bad name.wav"])
def test_smb_transfer_log_rejects_non_basename_wav(remote_name, tmp_path):
    # Arrange
    log_path = tmp_path / "smb.json"
    log_path.write_text(json.dumps({"tenant/call": {
        "tenant_id": "tenant", "call_id": "call", "status": "done",
        "started_at": "2026-08-18T12:01:02+00:00", "remote_name": remote_name,
    }}), encoding="utf-8")

    # Act / Assert
    assert transcript_batch.load_smb_audio_reference(log_path, "tenant", "call") is None


@pytest.mark.parametrize(
    "item",
    [
        None,
        {"tenant_id": "tenant", "call_id": "call", "status": "pending"},
        {"tenant_id": "other", "call_id": "call", "status": "done", "started_at": "2026-08-18T12:01:02+00:00", "remote_name": "2026-08-18-12-01-02-call-1-2.wav"},
        {"tenant_id": "tenant", "call_id": "other", "status": "done", "started_at": "2026-08-18T12:01:02+00:00", "remote_name": "2026-08-18-12-01-02-call-1-2.wav"},
        {"tenant_id": "tenant", "call_id": "call", "status": "done", "started_at": "invalid", "remote_name": "2026-08-18-12-01-02-call-1-2.wav"},
    ],
)
def test_smb_transfer_log_fails_closed_for_missing_pending_or_inconsistent_item(item, tmp_path):
    # Arrange
    log_path = tmp_path / "smb.json"
    log_path.write_text(json.dumps({} if item is None else {"tenant/call": item}), encoding="utf-8")

    # Act / Assert
    assert transcript_batch.load_smb_audio_reference(log_path, "tenant", "call") is None


@pytest.mark.asyncio
async def test_process_call_marks_consumed_only_after_database_and_smb(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    _wav_pair(call_dir)
    events = []

    async def transcribe_pair(*_args, **_kwargs):
        return [{"channel": "tx", "speaker": "atendente", "text": "ok", "confidence": 0.9,
                 "start_time": 0.0, "end_time": 1.0, "is_final": True, "extra_metadata": {}}]

    async def persist(*_args, **_kwargs):
        events.append("db")

    class Publisher:
        async def list_names(self, _remote_dir):
            arguments = (
                metadata["started_at"], metadata["call_id"],
                metadata["caller_number"], metadata["callee_number"],
            )
            return {transcript_batch.build_remote_name(*arguments, extension="wav")}

        async def publish(self, *_args, **_kwargs):
            events.append("smb")
            return {"remote_name": "call.md"}

    monkeypatch.setattr(transcript_batch, "transcribe_pair", transcribe_pair)
    monkeypatch.setattr(transcript_batch, "persist_segments", persist)
    monkeypatch.setattr(transcript_batch, "mark_consumed", lambda *_args: events.append("consumed"))
    metadata = _with_remote_reference({
        "call_id": "call", "tenant_id": "tenant", "started_at": datetime.now(timezone.utc),
        "caller_number": "1", "callee_number": "2", "database_id": "db-call",
    })

    # Act
    result = await transcript_batch.process_call(Publisher(), call_dir, metadata)

    # Assert
    assert result["status"] == "done"
    assert events == ["db", "smb", "consumed"]


@pytest.mark.asyncio
async def test_process_call_publishes_md_with_the_selected_collision_wav_base(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "abcdef123"
    _wav_pair(call_dir)
    metadata = {
        "call_id": "abcdef123", "tenant_id": "tenant",
        "started_at": datetime(2026, 8, 18, 12, 1, 2, tzinfo=timezone.utc),
        "caller_number": "1001", "callee_number": "2002", "database_id": "db-call",
    }
    _, base_md, collision_md = transcript_batch.build_transcript_remote_names("tenant", metadata)
    collision_wav = collision_md.removesuffix(".md") + ".wav"
    metadata.update({
        "remote_dir": "tenant/2026-08-18",
        "remote_wav_name": collision_wav,
        "remote_md_name": collision_md,
    })
    published_names = []

    class Publisher:
        async def list_names(self, _remote_dir):
            return {base_md.removesuffix(".md") + ".wav", collision_wav}

        async def publish(self, _path, _remote_dir, base_name, collision_name):
            published_names.append((base_name, collision_name))
            return {"remote_name": base_name}

    monkeypatch.setattr(transcript_batch, "transcribe_pair", lambda *_args: _async_value([{
        "channel": "tx", "speaker": "atendente", "text": "ok", "confidence": 0.9,
        "start_time": 0.0, "end_time": 1.0, "is_final": True, "extra_metadata": {},
    }]))
    monkeypatch.setattr(transcript_batch, "persist_segments", lambda *_args: _async_value(None))

    # Act
    result = await transcript_batch.process_call(Publisher(), call_dir, metadata)

    # Assert
    assert result["status"] == "done"
    assert published_names == [(collision_md, collision_md)]


@pytest.mark.asyncio
async def test_process_call_does_not_mark_consumed_when_smb_fails(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    _wav_pair(call_dir)
    marked = []
    monkeypatch.setattr(transcript_batch, "transcribe_pair", lambda *_args, **_kwargs: _async_value([{
        "channel": "rx", "speaker": "cliente", "text": "ok", "confidence": 0.8,
        "start_time": 0.0, "end_time": 1.0, "is_final": True, "extra_metadata": {},
    }]))
    monkeypatch.setattr(transcript_batch, "persist_segments", lambda *_args, **_kwargs: _async_value(None))
    monkeypatch.setattr(transcript_batch, "mark_consumed", lambda *_args: marked.append(True))

    class FailingPublisher:
        async def list_names(self, _remote_dir):
            arguments = (
                metadata["started_at"], metadata["call_id"],
                metadata["caller_number"], metadata["callee_number"],
            )
            return {transcript_batch.build_remote_name(*arguments, extension="wav")}

        async def publish(self, *_args, **_kwargs):
            raise OSError("SMB offline")

    metadata = _with_remote_reference({
        "call_id": "call", "tenant_id": "tenant", "started_at": datetime.now(timezone.utc),
        "caller_number": "1", "callee_number": "2", "database_id": "db-call",
    })

    # Act
    with pytest.raises(OSError, match="SMB offline"):
        await transcript_batch.process_call(FailingPublisher(), call_dir, metadata)

    # Assert
    assert marked == []


@pytest.mark.asyncio
async def test_process_call_publishes_terminal_markdown_for_silent_audio(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "silent"
    _wav_pair(call_dir)
    metadata = _with_remote_reference({
        "call_id": "silent", "tenant_id": "tenant", "started_at": datetime.now(timezone.utc),
        "caller_number": "1", "callee_number": "2", "database_id": "db-call",
    })
    published = []

    class Publisher:
        async def list_names(self, _remote_dir):
            return {metadata["remote_wav_name"]}

        async def publish(self, local_path, *_args):
            published.append(local_path.read_text(encoding="utf-8"))
            return {"remote_name": metadata["remote_md_name"]}

    monkeypatch.setattr(transcript_batch, "transcribe_pair", lambda *_args: _async_value([]))
    monkeypatch.setattr(transcript_batch, "persist_segments", lambda *_args: _async_value(None))

    # Act
    result = await transcript_batch.process_call(Publisher(), call_dir, metadata)

    # Assert
    assert result["segments"] == 0
    assert "Nenhuma fala detectada" in published[0]
    assert (call_dir / ".consumed-transcription").is_file()


async def _async_value(value):
    return value


def _with_remote_reference(metadata: dict) -> dict:
    arguments = (
        metadata["started_at"], metadata["call_id"],
        metadata["caller_number"], metadata["callee_number"],
    )
    wav_name = transcript_batch.build_remote_name(*arguments, extension="wav")
    return {
        **metadata,
        "remote_dir": transcript_batch.build_remote_directory(
            metadata["tenant_id"], metadata["started_at"]
        ),
        "remote_wav_name": wav_name,
        "remote_md_name": wav_name.removesuffix(".wav") + ".md",
    }


def test_worker_uses_exclusive_queue_and_single_concurrency():
    # Arrange / Act
    worker = transcript_batch.WorkerSettings

    # Assert
    assert worker.queue_name == "zenith:transcript"
    assert worker.max_jobs == 1
    assert worker.job_timeout > transcript_batch.settings.TRANSCRIPT_CALL_TIMEOUT_SECONDS


def test_tenant_schema_rejects_filesystem_injection():
    # Arrange / Act / Assert
    assert transcript_batch._tenant_schema("condominio_1") == "tenant_condominio_1"
    with pytest.raises(ValueError, match="tenant"):
        transcript_batch._tenant_schema("bad-name;drop")


@pytest.mark.asyncio
async def test_chunk_audio_preserves_all_pcm_frames_across_boundaries(tmp_path, monkeypatch):
    # Arrange
    source = tmp_path / "tx.wav"
    frame_count = 40_000
    with wave.open(str(source), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x00\x00" * frame_count)
    monkeypatch.setattr(transcript_batch.settings, "TRANSCRIPT_CHUNK_SECONDS", 1)

    # Act
    chunks = await transcript_batch.chunk_audio(source, tmp_path / "chunks", "tx")
    total_frames = 0
    for chunk in chunks:
        with wave.open(str(chunk), "rb") as audio:
            assert audio.getframerate() == 16_000
            assert audio.getnchannels() == 1
            total_frames += audio.getnframes()

    # Assert
    assert len(chunks) == 3
    assert total_frames == frame_count


@pytest.mark.asyncio
async def test_markdown_exists_lists_names_without_downloading_remote():
    # Arrange
    class Publisher:
        async def list_names(self, remote_dir):
            assert remote_dir == "tenant/2026-08-18"
            return {"call.wav", "call.md"}

    # Act
    exists = await transcript_batch.markdown_exists(
        Publisher(), "tenant/2026-08-18", "call.md", "call-alt.md"
    )

    # Assert
    assert exists


@pytest.mark.asyncio
async def test_concurrent_process_call_is_excluded_by_transcription_lease(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    _wav_pair(call_dir)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_owned(*_args):
        started.set()
        await release.wait()
        return {"status": "done"}

    monkeypatch.setattr(transcript_batch, "_process_owned_call", slow_owned)
    metadata = {"call_id": "call"}

    # Act
    first = asyncio.create_task(transcript_batch.process_call(object(), call_dir, metadata))
    await started.wait()
    second = await transcript_batch.process_call(object(), call_dir, metadata)
    release.set()
    first_result = await first

    # Assert
    assert second == {"status": "pending", "reason": "already_processing"}
    assert first_result == {"status": "done"}
    assert not (call_dir / ".transcription-processing").exists()


@pytest.mark.asyncio
async def test_process_call_timeout_cancels_work_and_releases_lease(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    _wav_pair(call_dir)
    cancelled = asyncio.Event()

    async def blocked(*_args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(transcript_batch, "_process_owned_call", blocked)
    monkeypatch.setattr(transcript_batch.settings, "TRANSCRIPT_CALL_TIMEOUT_SECONDS", 0.01)

    # Act
    result = await transcript_batch.process_call(object(), call_dir, {"call_id": "call"})

    # Assert
    assert result == {"status": "pending", "reason": "timeout"}
    assert cancelled.is_set()
    assert not (call_dir / ".transcription-processing").exists()


@pytest.mark.asyncio
async def test_transcribe_pair_offsets_each_chunk_and_orders_channels(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "call"
    _wav_pair(call_dir)
    monkeypatch.setattr(transcript_batch.settings, "TRANSCRIPT_CHUNK_SECONDS", 30)

    async def chunks(_source, output_dir, channel):
        paths = []
        for index in range(2 if channel == "tx" else 1):
            path = output_dir / f"{channel}-{index}.wav"
            frame_count = 481_280 if channel == "tx" and index == 0 else 160
            with wave.open(str(path), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(16_000)
                target.writeframes(b"\x00\x00" * frame_count)
            paths.append(path)
        return paths

    class Strategy:
        async def transcribe(self, content):
            return {"segments": [{
                "text": "fala", "start": 0.5, "end": 1.0, "confidence": 0.7,
            }]}

    monkeypatch.setattr(transcript_batch, "chunk_audio", chunks)

    # Act
    segments = await transcript_batch.transcribe_pair(call_dir, Strategy())

    # Assert
    assert [(item["channel"], item["start_time"]) for item in segments] == [
        ("rx", 0.5), ("tx", 0.5), ("tx", 30.58),
    ]


@pytest.mark.asyncio
async def test_transcribe_pair_fails_closed_on_whisper_error(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "call"
    _wav_pair(call_dir)

    async def one_chunk(_source, output_dir, channel):
        path = output_dir / f"{channel}.wav"
        path.write_bytes(b"audio")
        return [path]

    class Strategy:
        async def transcribe(self, _content):
            return {"error": "model unavailable"}

    monkeypatch.setattr(transcript_batch, "chunk_audio", one_chunk)

    # Act / Assert
    with pytest.raises(RuntimeError, match="model unavailable"):
        await transcript_batch.transcribe_pair(call_dir, Strategy())


@pytest.mark.asyncio
async def test_transcribe_pair_treats_silence_as_successful_empty_result(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "call"
    _wav_pair(call_dir)

    async def one_chunk(_source, output_dir, channel):
        path = output_dir / f"{channel}.wav"
        with wave.open(str(path), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(16_000)
            target.writeframes(b"\x00\x00" * 160)
        return [path]

    class Strategy:
        async def transcribe(self, _content):
            return {"segments": []}

    monkeypatch.setattr(transcript_batch, "chunk_audio", one_chunk)

    # Act
    result = await transcript_batch.transcribe_pair(call_dir, Strategy())

    # Assert
    assert result == []


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeSession:
    def __init__(self, results):
        self.results = iter(results)
        self.executed = []
        self.added = []
        self.flushed = False

    async def execute(self, statement, params=None):
        self.executed.append((statement, params))
        return _ScalarResult(next(self.results, None))

    def add_all(self, values):
        self.added.extend(values)

    async def flush(self):
        self.flushed = True


def _database_port(session, schemas):
    async def get_db(schema):
        schemas.append(schema)
        yield session

    return get_db


@pytest.mark.asyncio
async def test_database_ports_resolve_check_and_replace_transcripts(monkeypatch):
    # Arrange
    started = datetime(2026, 8, 18, 12, 0)
    call = SimpleNamespace(
        id="db-id", started_at=started, caller_number=None, callee_number="2002"
    )
    schemas = []
    metadata_session = _FakeSession([call])
    monkeypatch.setattr(
        transcript_batch, "get_tenant_db", _database_port(metadata_session, schemas)
    )

    # Act
    metadata = await transcript_batch.resolve_call_metadata("tenant_a", "call-a")

    # Assert
    assert metadata["started_at"].tzinfo == timezone.utc
    assert metadata["caller_number"] == "desconhecido"
    assert schemas == ["tenant_tenant_a"]

    # Arrange
    exists_session = _FakeSession(["transcript-id"])
    monkeypatch.setattr(
        transcript_batch, "get_tenant_db", _database_port(exists_session, [])
    )

    # Act / Assert
    assert await transcript_batch.transcripts_exist("tenant_a", "db-id")

    # Arrange
    persist_session = _FakeSession([None, None])
    monkeypatch.setattr(
        transcript_batch, "get_tenant_db", _database_port(persist_session, [])
    )
    segment = {
        "channel": "tx", "speaker": "atendente", "text": "olá", "confidence": 0.9,
        "start_time": 0.0, "end_time": 1.0, "is_final": True, "extra_metadata": {},
    }

    # Act
    await transcript_batch.persist_segments("tenant_a", "db-id", "call-a", [segment])

    # Assert
    assert "pg_advisory_xact_lock" in str(persist_session.executed[0][0])
    assert persist_session.executed[0][1] == {"call_id": "call-a"}
    assert persist_session.added[0].extra_metadata == {}
    assert persist_session.flushed


@pytest.mark.asyncio
async def test_run_cycle_processes_ready_calls_and_isolates_failure(monkeypatch, tmp_path):
    # Arrange
    good = tmp_path / "tenant" / "good"
    bad = tmp_path / "tenant" / "bad"
    _wav_pair(good)
    _wav_pair(bad)
    monkeypatch.setattr(transcript_batch.settings, "TRANSCRIPT_ENABLED", True)
    monkeypatch.setattr(transcript_batch.settings, "RECORDINGS_PATH", str(tmp_path))
    class Publisher:
        async def list_names(self, _remote_dir):
            return {"call.wav"}

    monkeypatch.setattr(transcript_batch, "SMBBackupStrategy", Publisher)
    monkeypatch.setattr(transcript_batch, "set_transcript_queue_size", lambda _count: None)
    monkeypatch.setattr(transcript_batch, "record_transcript_success", lambda: None)
    monkeypatch.setattr(transcript_batch, "record_transcript_failure", lambda _reason: None)
    monkeypatch.setattr(transcript_batch, "observe_transcript_latency", lambda _seconds: None)

    async def metadata(tenant_id, call_id):
        return {
            "tenant_id": tenant_id, "call_id": call_id, "database_id": call_id,
            "started_at": datetime.now(timezone.utc), "caller_number": "1", "callee_number": "2",
        }

    async def process(_publisher, _directory, call_metadata):
        if call_metadata["call_id"] == "bad":
            raise OSError("isolated")
        return {"status": "done"}

    monkeypatch.setattr(transcript_batch, "resolve_call_metadata", metadata)
    monkeypatch.setattr(transcript_batch, "load_smb_audio_reference", lambda *_args: {
        "remote_dir": "tenant/2026-08-18", "remote_wav_name": "call.wav",
        "remote_md_name": "call.md",
    })
    monkeypatch.setattr(transcript_batch, "transcripts_exist", lambda *_args: _async_value(False))
    monkeypatch.setattr(transcript_batch, "process_call", process)

    # Act
    result = await transcript_batch._run_cycle({})

    # Assert
    assert result == {"status": "completed", "calls_seen": 2, "completed": 1, "failed": 1}


@pytest.mark.asyncio
async def test_run_cycle_repairs_consumed_marker_when_database_and_smb_are_complete(
    monkeypatch, tmp_path
):
    # Arrange
    call_dir = tmp_path / "tenant" / "abcdef123"
    _wav_pair(call_dir)
    metadata = {
        "tenant_id": "tenant", "call_id": "abcdef123", "database_id": "db-call",
        "started_at": datetime(2026, 8, 18, 12, 1, 2, tzinfo=timezone.utc),
        "caller_number": "1001", "callee_number": "2002",
    }
    _, base_md, _ = transcript_batch.build_transcript_remote_names("tenant", metadata)
    audio_name = base_md.removesuffix(".md") + ".wav"

    class Publisher:
        async def list_names(self, _remote_dir):
            return {audio_name, base_md}

    monkeypatch.setattr(transcript_batch.settings, "TRANSCRIPT_ENABLED", True)
    monkeypatch.setattr(transcript_batch.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(transcript_batch, "SMBBackupStrategy", Publisher)
    monkeypatch.setattr(transcript_batch, "set_transcript_queue_size", lambda _count: None)
    monkeypatch.setattr(transcript_batch, "observe_transcript_latency", lambda _seconds: None)
    monkeypatch.setattr(transcript_batch, "resolve_call_metadata", lambda *_args: _async_value(metadata))
    monkeypatch.setattr(transcript_batch, "load_smb_audio_reference", lambda *_args: {
        "remote_dir": "tenant/2026-08-18", "remote_wav_name": audio_name,
        "remote_md_name": base_md,
    })
    monkeypatch.setattr(transcript_batch, "transcripts_exist", lambda *_args: _async_value(True))

    async def must_not_process(*_args):
        raise AssertionError("completed call must only repair its marker")

    monkeypatch.setattr(transcript_batch, "process_call", must_not_process)

    # Act
    result = await transcript_batch._run_cycle({})

    # Assert
    assert result["completed"] == 0
    assert (call_dir / ".consumed-transcription").is_file()


@pytest.mark.asyncio
async def test_run_cycle_does_not_claim_another_calls_base_wav_on_collision(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "abcdef123"
    _wav_pair(call_dir)
    metadata = {
        "tenant_id": "tenant", "call_id": "abcdef123", "database_id": "db-call",
        "started_at": datetime(2026, 8, 18, 12, 1, 2, tzinfo=timezone.utc),
        "caller_number": "1001", "callee_number": "2002",
    }
    base_wav = "2026-08-18-12-01-02-abcdef-1001-2002.wav"
    collision_wav = "2026-08-18-12-01-02-abcdef-1001-2002-123.wav"
    processed = []

    class Publisher:
        async def list_names(self, _remote_dir):
            return {base_wav}

    monkeypatch.setattr(transcript_batch.settings, "TRANSCRIPT_ENABLED", True)
    monkeypatch.setattr(transcript_batch.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(transcript_batch, "SMBBackupStrategy", Publisher)
    monkeypatch.setattr(transcript_batch, "set_transcript_queue_size", lambda _count: None)
    monkeypatch.setattr(transcript_batch, "observe_transcript_latency", lambda _seconds: None)
    monkeypatch.setattr(transcript_batch, "resolve_call_metadata", lambda *_args: _async_value(metadata))
    log_path = tmp_path / "smb-transfer.json"
    log_path.write_text(json.dumps({"tenant/abcdef123": {
        "tenant_id": "tenant", "call_id": "abcdef123", "status": "done",
        "started_at": "2026-08-18T12:01:02+00:00", "remote_name": collision_wav,
    }}), encoding="utf-8")
    monkeypatch.setattr(transcript_batch.settings, "SMB_TRANSFER_LOG_PATH", str(log_path))

    async def process(*_args):
        processed.append(True)
        return {"status": "done"}

    monkeypatch.setattr(transcript_batch, "process_call", process)

    # Act
    result = await transcript_batch._run_cycle({})

    # Assert
    assert result["completed"] == 0
    assert processed == []


@pytest.mark.asyncio
async def test_run_cycle_without_transfer_log_does_not_query_postgres(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    _wav_pair(call_dir)
    empty_log = tmp_path / "smb-transfer.json"
    empty_log.write_text("{}", encoding="utf-8")
    metadata_calls = []
    monkeypatch.setattr(transcript_batch.settings, "TRANSCRIPT_ENABLED", True)
    monkeypatch.setattr(transcript_batch.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(transcript_batch.settings, "SMB_TRANSFER_LOG_PATH", str(empty_log))
    monkeypatch.setattr(transcript_batch, "SMBBackupStrategy", object)
    monkeypatch.setattr(transcript_batch, "set_transcript_queue_size", lambda _count: None)
    monkeypatch.setattr(transcript_batch, "observe_transcript_latency", lambda _seconds: None)

    async def metadata(*_args):
        metadata_calls.append(True)

    monkeypatch.setattr(transcript_batch, "resolve_call_metadata", metadata)

    # Act
    result = await transcript_batch._run_cycle({})

    # Assert
    assert result["completed"] == 0
    assert metadata_calls == []


@pytest.mark.asyncio
async def test_silent_call_marker_and_md_prevent_retry_on_next_cycle(monkeypatch, tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "silent"
    _wav_pair(call_dir)
    mark = call_dir / ".consumed-transcription"
    transcript_batch.mark_consumed(call_dir, "transcription")
    wav_name = "2026-08-18-12-01-02-silent-1-2.wav"
    md_name = wav_name.removesuffix(".wav") + ".md"
    log_path = tmp_path / "smb-transfer.json"
    log_path.write_text(json.dumps({"tenant/silent": {
        "tenant_id": "tenant", "call_id": "silent", "status": "done",
        "started_at": "2026-08-18T12:01:02+00:00", "remote_name": wav_name,
    }}), encoding="utf-8")

    class Publisher:
        async def list_names(self, _remote_dir):
            return {wav_name, md_name}

    metadata = {
        "tenant_id": "tenant", "call_id": "silent", "database_id": "db-call",
        "started_at": datetime(2026, 8, 18, 12, 1, 2, tzinfo=timezone.utc),
        "caller_number": "1", "callee_number": "2",
    }
    monkeypatch.setattr(transcript_batch.settings, "TRANSCRIPT_ENABLED", True)
    monkeypatch.setattr(transcript_batch.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(transcript_batch.settings, "SMB_TRANSFER_LOG_PATH", str(log_path))
    monkeypatch.setattr(transcript_batch, "SMBBackupStrategy", Publisher)
    monkeypatch.setattr(transcript_batch, "set_transcript_queue_size", lambda _count: None)
    monkeypatch.setattr(transcript_batch, "observe_transcript_latency", lambda _seconds: None)
    monkeypatch.setattr(transcript_batch, "resolve_call_metadata", lambda *_args: _async_value(metadata))

    async def must_not_query_or_process(*_args):
        raise AssertionError("terminal silent call must not retry")

    monkeypatch.setattr(transcript_batch, "transcripts_exist", must_not_query_or_process)
    monkeypatch.setattr(transcript_batch, "process_call", must_not_query_or_process)

    # Act
    result = await transcript_batch._run_cycle({})

    # Assert
    assert mark.is_file()
    assert result["completed"] == 0


@pytest.mark.asyncio
async def test_run_cycle_disabled_and_lock_are_noops(monkeypatch):
    # Arrange
    monkeypatch.setattr(transcript_batch.settings, "TRANSCRIPT_ENABLED", False)

    # Act / Assert
    assert await transcript_batch._run_cycle({}) == {"status": "disabled"}
    async with transcript_batch._cycle_lock:
        assert await transcript_batch.run_transcript_cycle({}) == {"status": "already_running"}
