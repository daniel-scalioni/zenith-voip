import asyncio
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from arq.constants import default_queue_name

from src.audio.recording_lifecycle import acquire_lease, release_lease
from src.workers import smb_sync


def test_build_remote_name_sanitizes_and_uses_collision_suffix():
    # Arrange
    started_at = datetime(2026, 7, 28, 13, 5, 9, tzinfo=timezone.utc)

    # Act
    base = smb_sync.build_remote_name(started_at, "abcdef123456", "10/01", "")
    collision = smb_sync.build_remote_name(
        started_at, "abcdef123456", "10/01", "", include_collision_suffix=True
    )

    # Assert
    assert base == "2026-07-28-13-05-09-abcdef-10_01-desconhecido.wav"
    assert collision == "2026-07-28-13-05-09-abcdef-10_01-desconhecido-1234.wav"


def test_build_remote_directory_is_tenant_and_date_scoped():
    # Arrange
    started_at = datetime(2026, 7, 28, tzinfo=timezone.utc)

    # Act
    result = smb_sync.build_remote_directory("tenant/../../other", started_at)

    # Assert
    assert result == "tenant_.._.._other/2026-07-28"


def test_transfer_log_recovers_corrupt_json(tmp_path, caplog):
    # Arrange
    path = tmp_path / "smb_transfer_log.json"
    path.write_text("{invalid", encoding="utf-8")

    # Act
    state = smb_sync.load_transfer_log(path)

    # Assert
    assert state == {}
    assert list(tmp_path.glob("smb_transfer_log.json.corrupt-*"))
    assert "corrupt" in caplog.text.lower()


def test_transfer_log_writes_atomically_and_prunes_done(tmp_path):
    # Arrange
    path = tmp_path / "smb_transfer_log.json"
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    recent = datetime.now(timezone.utc).isoformat()
    state = {
        "tenant/old": {"status": "done", "updated_at": old},
        "tenant/new": {"status": "pending", "updated_at": recent},
        "tenant/failed": {"status": "failed", "updated_at": old},
    }

    # Act
    smb_sync.save_transfer_log(path, state)
    loaded = smb_sync.load_transfer_log(path)
    pruned = smb_sync.prune_transfer_log(loaded, retention_days=7)

    # Assert
    assert json.loads(path.read_text(encoding="utf-8")) == state
    assert set(pruned) == {"tenant/new"}
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.asyncio
async def test_bandwidth_limiter_uses_offsets_and_truncates_only_first_chunk():
    # Arrange
    calls = []

    class Connection:
        def storeFileFromOffset(self, service, path, stream, offset, truncate, timeout):
            calls.append((service, path, stream.read(), offset, truncate, timeout))

    limiter = smb_sync.BandwidthLimiter(
        megabytes_per_second=1024,
        chunk_size=4,
        sleep=AsyncMock(),
    )

    # Act
    await limiter.store(Connection(), "share", "audio.tmp", io.BytesIO(b"abcdefghij"))

    # Assert
    assert [(item[3], item[4], item[2]) for item in calls] == [
        (0, True, b"abcd"),
        (4, False, b"efgh"),
        (8, False, b"ij"),
    ]


@pytest.mark.asyncio
async def test_smb_strategy_publishes_under_base_path_and_confirms_checksum(
    tmp_path, monkeypatch
):
    # Arrange
    local = tmp_path / "stereo.wav"
    local.write_bytes(b"stereo-audio")

    class Entry:
        def __init__(self, filename):
            self.filename = filename

    class Connection:
        def __init__(self, *_args, **_kwargs):
            self.files = {}
            self.directories = set()
            self.closed = False

        def connect(self, *_args, **_kwargs):
            return True

        def createDirectory(self, _share, path, timeout):
            self.directories.add(path)

        def listPath(self, _share, path, timeout):
            prefix = path.rstrip("/") + "/"
            names = [
                key[len(prefix) :]
                for key in self.files
                if key.startswith(prefix) and "/" not in key[len(prefix) :]
            ]
            return [Entry("."), Entry(".."), *(Entry(name) for name in names)]

        def storeFileFromOffset(
            self, _share, path, stream, offset, truncate, timeout
        ):
            current = b"" if truncate else self.files.get(path, b"")
            payload = bytearray(current)
            if len(payload) < offset:
                payload.extend(b"\x00" * (offset - len(payload)))
            data = stream.read()
            payload[offset : offset + len(data)] = data
            self.files[path] = bytes(payload)

        def rename(self, _share, old_path, new_path, timeout):
            self.files[new_path] = self.files.pop(old_path)

        def retrieveFile(self, _share, path, target, timeout):
            target.write(self.files[path])
            return None, len(self.files[path])

        def deleteFiles(self, _share, path, delete_matching_folders, timeout):
            self.files.pop(path, None)

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(smb_sync.settings, "SMB_PATH", "Audios_Atendimento")
    monkeypatch.setattr(smb_sync.settings, "SMB_SHARE", "backup$")
    monkeypatch.setattr(smb_sync.settings, "SMB_BANDWIDTH_LIMIT_MBS", 1024)
    strategy = smb_sync.SMBBackupStrategy(connection_factory=lambda *_a, **_k: connection)

    # Act
    result = await strategy.publish(
        local,
        "tenant/2026-07-28",
        "base.wav",
        "base-1234.wav",
    )

    # Assert
    remote = "Audios_Atendimento/tenant/2026-07-28/base.wav"
    assert connection.files[remote] == b"stereo-audio"
    assert result["sha256"] == hashlib.sha256(b"stereo-audio").hexdigest()
    assert connection.closed is True


@pytest.mark.asyncio
async def test_corrupt_remote_temporary_is_deleted_before_rename():
    # Arrange
    deleted = []

    class Connection:
        def retrieveFile(self, _share, _path, target, timeout):
            target.write(b"corrupt")

        def deleteFiles(self, _share, path, delete_matching_folders, timeout):
            deleted.append(path)

        def rename(self, *_args, **_kwargs):
            raise AssertionError("corrupt temporary must not be renamed")

    expected = hashlib.sha256(b"expected").hexdigest()

    # Act / Assert
    with pytest.raises(OSError, match="checksum"):
        await smb_sync.verify_remote_temporary_and_rename(
            Connection(),
            "backup",
            "audio.tmp",
            "audio.wav",
            expected,
        )
    assert deleted == ["audio.tmp"]


def test_lease_validity_and_corruption(tmp_path, caplog):
    # Arrange
    now = datetime(2026, 7, 28, 13, 0, tzinfo=timezone.utc)
    call_dir = tmp_path / "call"
    call_dir.mkdir()
    lease = smb_sync.write_lease(call_dir, "call-1", now=now)

    # Act
    valid = smb_sync.has_valid_lease(call_dir, now=now + timedelta(seconds=119))
    expired = smb_sync.has_valid_lease(call_dir, now=now + timedelta(seconds=121))
    lease.write_text("{bad", encoding="utf-8")
    corrupt = smb_sync.has_valid_lease(call_dir, now=now)

    # Assert
    assert valid is True
    assert expired is False
    assert corrupt is False
    assert "lease" in caplog.text.lower()


@pytest.mark.asyncio
async def test_lease_renewal_failure_is_logged_and_aborts_stage(tmp_path, monkeypatch, caplog):
    # Arrange
    calls = 0

    async def controlled_sleep(_seconds):
        nonlocal calls
        calls += 1

    def fail_write(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(smb_sync.asyncio, "sleep", controlled_sleep)
    monkeypatch.setattr(smb_sync, "write_lease", fail_write)

    # Act / Assert
    with pytest.raises(OSError):
        await smb_sync._renew_lease(tmp_path, "call")
    assert "renew" in caplog.text.lower()


@pytest.mark.asyncio
async def test_cycle_lock_returns_already_running(monkeypatch):
    # Arrange
    first_started = asyncio.Event()
    release = asyncio.Event()

    async def slow_cycle(*_args, **_kwargs):
        first_started.set()
        await release.wait()
        return {"status": "completed"}

    monkeypatch.setattr(smb_sync, "_run_cycle", slow_cycle)

    # Act
    first = asyncio.create_task(smb_sync.run_smb_sync({}))
    await first_started.wait()
    second = await smb_sync.run_smb_sync({})
    release.set()
    await first

    # Assert
    assert second == {"status": "already_running"}


@pytest.mark.asyncio
async def test_generate_stereo_publishes_only_after_success(tmp_path, monkeypatch):
    # Arrange
    tx = tmp_path / "tx.wav"
    rx = tmp_path / "rx.wav"
    tx.write_bytes(b"tx")
    rx.write_bytes(b"rx")

    class Process:
        returncode = 0

        async def communicate(self):
            Path(self.output_path).write_bytes(b"stereo")
            return b"", b""

    async def create_process(*args, **_kwargs):
        process = Process()
        process.output_path = args[-1]
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)

    # Act
    result = await smb_sync.generate_stereo(tx, rx)

    # Assert
    assert result == tmp_path / "stereo.wav"
    assert result.read_bytes() == b"stereo"
    assert not (tmp_path / "stereo.tmp.wav").exists()


@pytest.mark.asyncio
async def test_generate_stereo_terminates_ffmpeg_when_cancelled(tmp_path, monkeypatch):
    # Arrange
    tx = tmp_path / "tx.wav"
    rx = tmp_path / "rx.wav"
    tx.write_bytes(b"tx")
    rx.write_bytes(b"rx")
    communicating = asyncio.Event()

    class Process:
        returncode = None
        killed = False
        waited = False

        async def communicate(self):
            communicating.set()
            await asyncio.Future()

        def kill(self):
            self.killed = True

        async def wait(self):
            self.waited = True
            self.returncode = -9

    process = Process()

    async def create_process(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    task = asyncio.create_task(smb_sync.generate_stereo(tx, rx))
    await communicating.wait()

    # Act
    task.cancel()

    # Assert
    with pytest.raises(asyncio.CancelledError):
        await task
    assert process.killed is True
    assert process.waited is True
    assert not (tmp_path / "stereo.tmp.wav").exists()


@pytest.mark.asyncio
async def test_ensure_mono_pair_retries_raw_conversion(tmp_path, monkeypatch):
    # Arrange
    tx_raw = tmp_path / "tx.raw"
    tx_raw.write_bytes(b"raw")
    (tmp_path / "rx.wav").write_bytes(b"rx")

    async def convert(path):
        result = Path(path).with_suffix(".wav")
        result.write_bytes(b"tx")
        return str(result)

    monkeypatch.setattr(smb_sync, "_convert_to_wav", convert)

    # Act
    pair = await smb_sync.ensure_mono_pair(tmp_path)

    # Assert
    assert pair == (tmp_path / "tx.wav", tmp_path / "rx.wav")


@pytest.mark.asyncio
async def test_ensure_mono_pair_does_not_race_active_uploader_conversion(tmp_path, monkeypatch):
    # Arrange
    (tmp_path / "tx.raw").write_bytes(b"raw")
    lease = acquire_lease(tmp_path, "conversion", "call")
    convert = AsyncMock()
    monkeypatch.setattr(smb_sync, "_convert_to_wav", convert)

    # Act
    pair = await smb_sync.ensure_mono_pair(tmp_path)

    # Assert
    assert pair is None
    convert.assert_not_awaited()
    release_lease(tmp_path, "conversion", lease.owner)


@pytest.mark.asyncio
async def test_resolve_call_metadata_uses_repository_then_safe_fallback(tmp_path, monkeypatch):
    # Arrange
    started = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        smb_sync,
        "_load_call_metadata",
        AsyncMock(
            return_value={
                "started_at": started,
                "caller_number": None,
                "callee_number": "2099",
            }
        ),
    )

    # Act
    result = await smb_sync.resolve_call_metadata("tenant", "call", tmp_path)

    # Assert
    assert result == {
        "started_at": started,
        "caller_number": "desconhecido",
        "callee_number": "2099",
    }


def test_resolve_collision_never_overwrites_divergent_second_name():
    # Arrange
    local_sha = hashlib.sha256(b"local").hexdigest()

    def remote_sha(name):
        return hashlib.sha256(name.encode()).hexdigest()

    # Act
    with pytest.raises(smb_sync.RemoteCollisionError):
        smb_sync.resolve_remote_name(
            "base.wav",
            "base-1234.wav",
            local_sha,
            remote_sha,
        )


def test_circuit_breaker_opens_after_five_failures_and_recovers():
    # Arrange
    breaker = smb_sync.CircuitBreaker(failure_threshold=5, reset_seconds=300)

    # Act
    for _ in range(5):
        breaker.record_failure(now=100)

    # Assert
    assert breaker.allows_request(now=399) is False
    assert breaker.allows_request(now=400) is True
    assert breaker.failures == 0


@pytest.mark.asyncio
async def test_process_call_removes_stereo_only_after_checksum(tmp_path, monkeypatch):
    # Arrange
    stereo = tmp_path / "stereo.wav"
    stereo.write_bytes(b"stereo")
    (tmp_path / "tx.wav").write_bytes(b"tx")
    (tmp_path / "rx.wav").write_bytes(b"rx")
    strategy = AsyncMock()
    strategy.publish.return_value = {"sha256": hashlib.sha256(b"stereo").hexdigest()}
    monkeypatch.setattr(smb_sync, "generate_stereo", AsyncMock(return_value=stereo))

    # Act
    result = await smb_sync.process_call(
        strategy,
        tenant_id="tenant",
        call_id="call-id",
        call_dir=tmp_path,
        metadata={},
    )

    # Assert
    assert result["status"] == "done"
    assert not stereo.exists()
    assert (tmp_path / ".consumed-smb").exists()


@pytest.mark.asyncio
async def test_process_call_preserves_stereo_on_publish_failure(tmp_path, monkeypatch):
    # Arrange
    stereo = tmp_path / "stereo.wav"
    stereo.write_bytes(b"stereo")
    (tmp_path / "tx.wav").write_bytes(b"tx")
    (tmp_path / "rx.wav").write_bytes(b"rx")
    strategy = AsyncMock()
    strategy.publish.side_effect = OSError("offline")
    monkeypatch.setattr(smb_sync, "generate_stereo", AsyncMock(return_value=stereo))
    monkeypatch.setattr(smb_sync, "RETRY_DELAYS_SECONDS", (0, 0, 0))

    # Act / Assert
    with pytest.raises(OSError):
        await smb_sync.process_call(
            strategy,
            tenant_id="tenant",
            call_id="call-id",
            call_dir=tmp_path,
            metadata={},
        )
    assert stereo.exists()
    assert not (tmp_path / ".consumed-smb").exists()


@pytest.mark.asyncio
async def test_remote_temporary_requires_two_observations(tmp_path, monkeypatch):
    # Arrange
    now = datetime(2026, 8, 14, tzinfo=timezone.utc)
    deleted = []

    class Item:
        filename = "call.wav.tmp"

    class Connection:
        def listPath(self, *_args, **_kwargs):
            return [Item()]

        def deleteFiles(self, _share, path, *_args):
            deleted.append(path)

        def close(self):
            pass

    strategy = smb_sync.SMBBackupStrategy(connection_factory=lambda *_a, **_k: None)
    monkeypatch.setattr(strategy, "_connect", lambda: Connection())

    # Act
    first = await strategy.cleanup_remote_temporaries("tenant/day", ["call.wav"], {}, now=now)
    second = await strategy.cleanup_remote_temporaries(
        "tenant/day", ["call.wav"], first,
        now=now + timedelta(seconds=smb_sync.settings.RECORDING_CLEANUP_ROUND_SECONDS),
    )

    # Assert
    assert first == {"call.wav.tmp": now.isoformat()}
    assert second == {}
    assert deleted == [strategy._join_path(smb_sync.settings.SMB_PATH, "tenant/day", "call.wav.tmp")]


@pytest.mark.asyncio
async def test_remote_temporary_scan_creates_first_backup_directory(monkeypatch):
    # Arrange
    events = []

    class Connection:
        def createDirectory(self, _share, path, **_kwargs):
            events.append(("create", path))

        def listPath(self, _share, path, **_kwargs):
            events.append(("list", path))
            return []

        def close(self):
            pass

    strategy = smb_sync.SMBBackupStrategy(connection_factory=lambda *_a, **_k: None)
    monkeypatch.setattr(strategy, "_connect", lambda: Connection())

    # Act
    candidates = await strategy.cleanup_remote_temporaries(
        "new-tenant/2026-08-14", ["call.wav"], {}
    )

    # Assert
    full_path = strategy._join_path(
        smb_sync.settings.SMB_PATH, "new-tenant/2026-08-14"
    )
    assert candidates == {}
    assert ("create", full_path) in events
    assert events.index(("create", full_path)) < events.index(("list", full_path))


@pytest.mark.asyncio
async def test_remote_temporary_scan_accepts_existing_parent_directories(monkeypatch):
    # Arrange
    events = []
    root = smb_sync.settings.SMB_PATH
    tenant = f"{root}/known-tenant"
    date = f"{tenant}/2026-08-14"

    class Connection:
        def createDirectory(self, _share, path, **_kwargs):
            events.append(("create", path))
            if path in {root, tenant}:
                raise smb_sync.OperationFailure("already exists", [])

        def listPath(self, _share, path, **_kwargs):
            events.append(("list", path))
            return []

        def close(self):
            pass

    strategy = smb_sync.SMBBackupStrategy(connection_factory=lambda *_a, **_k: None)
    monkeypatch.setattr(strategy, "_connect", lambda: Connection())

    # Act
    candidates = await strategy.cleanup_remote_temporaries(
        "known-tenant/2026-08-14", ["call.wav"], {}
    )

    # Assert
    assert candidates == {}
    assert events[:5] == [
        ("create", root),
        ("list", root),
        ("create", tenant),
        ("list", tenant),
        ("create", date),
    ]
    assert events[-1] == ("list", date)


@pytest.mark.asyncio
async def test_remote_directory_permission_failure_is_not_hidden(monkeypatch):
    # Arrange
    class Connection:
        def createDirectory(self, *_args, **_kwargs):
            raise smb_sync.OperationFailure("create denied", [])

        def listPath(self, *_args, **_kwargs):
            raise PermissionError("list denied")

        def close(self):
            pass

    strategy = smb_sync.SMBBackupStrategy(connection_factory=lambda *_a, **_k: None)
    monkeypatch.setattr(strategy, "_connect", lambda: Connection())

    # Act / Assert
    with pytest.raises(PermissionError, match="list denied"):
        await strategy.cleanup_remote_temporaries(
            "denied-tenant/2026-08-14", ["call.wav"], {}
        )


@pytest.mark.asyncio
async def test_publish_failure_carries_remote_candidate_for_next_cycle(tmp_path, monkeypatch):
    # Arrange
    (tmp_path / "tx.wav").write_bytes(b"tx")
    (tmp_path / "rx.wav").write_bytes(b"rx")
    stereo = tmp_path / "stereo.wav"
    stereo.write_bytes(b"stereo")
    strategy = AsyncMock()
    strategy.cleanup_remote_temporaries.return_value = {"call.wav.tmp": "2026-08-14T00:00:00+00:00"}
    strategy.publish.side_effect = OSError("offline")
    monkeypatch.setattr(smb_sync, "generate_stereo", AsyncMock(return_value=stereo))
    monkeypatch.setattr(smb_sync, "RETRY_DELAYS_SECONDS", ())

    # Act / Assert
    with pytest.raises(OSError) as raised:
        await smb_sync._process_call_unbounded(strategy, "tenant", "call", tmp_path, {})
    assert raised.value.remote_tmp_candidates == {"call.wav.tmp": "2026-08-14T00:00:00+00:00"}


@pytest.mark.asyncio
async def test_process_call_enforces_global_timeout(tmp_path, monkeypatch):
    # Arrange
    async def blocked(*_args, **_kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(smb_sync, "_process_call_unbounded", blocked)

    # Act
    result = await smb_sync.process_call(
        AsyncMock(),
        tenant_id="tenant",
        call_id="call-id",
        call_dir=tmp_path,
        metadata={},
        timeout_seconds=0.01,
    )

    # Assert
    assert result["status"] == "pending"
    assert result["reason"] == "timeout"


@pytest.mark.asyncio
async def test_run_cycle_disabled_does_not_touch_storage(monkeypatch):
    # Arrange
    monkeypatch.setattr(smb_sync.settings, "SMB_ENABLED", False)

    # Act
    result = await smb_sync._run_cycle({})

    # Assert
    assert result == {"status": "disabled"}


@pytest.mark.asyncio
async def test_run_cycle_records_success(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    (call_dir / "tx.wav").write_bytes(b"tx")
    (call_dir / "rx.wav").write_bytes(b"rx")
    log_path = tmp_path / "logs" / "smb_transfer_log.json"
    monkeypatch.setattr(smb_sync.settings, "SMB_ENABLED", True)
    monkeypatch.setattr(smb_sync.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(smb_sync.settings, "SMB_TRANSFER_LOG_PATH", str(log_path))
    monkeypatch.setattr(smb_sync, "SMBBackupStrategy", lambda: AsyncMock())
    monkeypatch.setattr(
        smb_sync,
        "resolve_call_metadata",
        AsyncMock(
            return_value={
                "started_at": datetime.now(timezone.utc),
                "caller_number": "1001",
                "callee_number": "2099",
            }
        ),
    )
    monkeypatch.setattr(
        smb_sync,
        "process_call",
        AsyncMock(return_value={"status": "done", "sha256": "abc"}),
    )
    smb_sync._circuit_breaker.reset()

    # Act
    result = await smb_sync._run_cycle({})

    # Assert
    assert result["completed"] == 1
    state = json.loads(log_path.read_text(encoding="utf-8"))
    assert state["tenant/call"]["status"] == "done"


@pytest.mark.asyncio
async def test_run_cycle_ignores_active_and_legacy_directories_without_log_entry(tmp_path, monkeypatch):
    # Arrange
    active_dir = tmp_path / "tenant" / "active-call"
    active_dir.mkdir(parents=True)
    (active_dir / "tx.raw").write_bytes(b"stable")
    (active_dir / "rx.raw").write_bytes(b"stable")
    capture = acquire_lease(active_dir, "capture", "active-call")
    legacy_dir = tmp_path / "tenant" / "legacy-call"
    legacy_dir.mkdir()
    (legacy_dir / "tx.mp3").write_bytes(b"legacy")
    (legacy_dir / "rx.mp3").write_bytes(b"legacy")
    log_path = tmp_path / "logs" / "smb_transfer_log.json"
    process = AsyncMock(return_value={"status": "done", "sha256": "unexpected"})
    metadata = AsyncMock(return_value={
        "started_at": datetime(2026, 8, 17, tzinfo=timezone.utc),
        "caller_number": "1001",
        "callee_number": "2001",
    })
    monkeypatch.setattr(smb_sync.settings, "SMB_ENABLED", True)
    monkeypatch.setattr(smb_sync.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(smb_sync.settings, "SMB_TRANSFER_LOG_PATH", str(log_path))
    monkeypatch.setattr(smb_sync, "SMBBackupStrategy", lambda: AsyncMock())
    monkeypatch.setattr(smb_sync, "resolve_call_metadata", metadata)
    monkeypatch.setattr(smb_sync, "process_call", process)
    smb_sync._circuit_breaker.reset()

    # Act
    try:
        result = await smb_sync._run_cycle({})
    finally:
        release_lease(active_dir, "capture", capture.owner)

    # Assert
    assert result == {"status": "completed", "calls_seen": 2, "completed": 0, "failed": 0}
    assert not log_path.exists()
    process.assert_not_awaited()
    metadata.assert_not_awaited()
    assert (active_dir / "tx.raw").read_bytes() == b"stable"
    assert not (active_dir / ".smb-processing").exists()


@pytest.mark.asyncio
async def test_run_cycle_does_not_log_when_conversion_wins_after_discovery(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant" / "racing-call"
    call_dir.mkdir(parents=True)
    (call_dir / "tx.raw").write_bytes(b"tx")
    (call_dir / "rx.raw").write_bytes(b"rx")
    log_path = tmp_path / "logs" / "smb_transfer_log.json"
    conversion = None

    async def metadata_with_racing_lease(_tenant_id, _call_id, _call_dir):
        nonlocal conversion
        conversion = acquire_lease(call_dir, "conversion", "racing-call")
        return {
            "started_at": datetime(2026, 8, 17, tzinfo=timezone.utc),
            "caller_number": "1001",
            "callee_number": "2001",
        }

    strategy = AsyncMock()
    monkeypatch.setattr(smb_sync.settings, "SMB_ENABLED", True)
    monkeypatch.setattr(smb_sync.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(smb_sync.settings, "SMB_TRANSFER_LOG_PATH", str(log_path))
    monkeypatch.setattr(smb_sync, "SMBBackupStrategy", lambda: strategy)
    monkeypatch.setattr(smb_sync, "resolve_call_metadata", metadata_with_racing_lease)
    smb_sync._circuit_breaker.reset()

    # Act
    try:
        result = await smb_sync._run_cycle({})
    finally:
        if conversion is not None:
            release_lease(call_dir, "conversion", conversion.owner)

    # Assert
    assert result == {"status": "completed", "calls_seen": 1, "completed": 0, "failed": 0}
    assert not log_path.exists()
    strategy.publish.assert_not_awaited()


def test_worker_settings_declares_exclusive_smb_queue():
    # Arrange
    worker_settings = smb_sync.WorkerSettings

    # Act
    queue_name = getattr(worker_settings, "queue_name", None)

    # Assert
    assert queue_name == "zenith:smb-sync"


@pytest.mark.asyncio
async def test_t080_missing_local_source_remains_pending_without_smb_copy(tmp_path):
    # Arrange
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    (call_dir / "rx.wav").write_bytes(b"rx-audio")
    smb_port = AsyncMock()

    # Act
    result = await smb_sync.process_call(
        smb_port,
        tenant_id="tenant",
        call_id="call",
        call_dir=call_dir,
        metadata={},
    )

    # Assert
    assert result == {"status": "pending", "reason": "mono_pair_incomplete"}
    smb_port.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_t080_smb_operation_failure_is_sanitized_in_log_and_state(
    tmp_path, monkeypatch, caplog
):
    # Arrange
    import wave

    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    for channel in ("tx", "rx"):
        with wave.open(str(call_dir / f"{channel}.wav"), "wb") as source:
            source.setnchannels(1)
            source.setsampwidth(2)
            source.setframerate(16000)
            source.writeframes(b"\x00\x00" * 800)
    log_path = tmp_path / "logs" / "smb_transfer_log.json"
    smb_port = AsyncMock()
    smb_port.publish.side_effect = smb_sync.OperationFailure(
        "SMB host=connection-sentinel user=credential-sentinel",
        [],
    )
    monkeypatch.setattr(smb_sync.settings, "SMB_ENABLED", True)
    monkeypatch.setattr(smb_sync.settings, "RECORDINGS_PATH", str(tmp_path))
    monkeypatch.setattr(smb_sync.settings, "SMB_TRANSFER_LOG_PATH", str(log_path))
    monkeypatch.setattr(smb_sync, "SMBBackupStrategy", lambda: smb_port)
    monkeypatch.setattr(
        smb_sync,
        "resolve_call_metadata",
        AsyncMock(
            return_value={
                "started_at": datetime(2026, 7, 31, tzinfo=timezone.utc),
                "caller_number": "1001",
                "callee_number": "2099",
            }
        ),
    )
    smb_sync._circuit_breaker.reset()
    caplog.set_level(smb_sync.logging.WARNING)

    # Act
    result = await smb_sync._run_cycle({})

    # Assert
    assert result["failed"] == 1
    state = json.loads(log_path.read_text(encoding="utf-8"))
    assert state["tenant/call"]["status"] == "pending"
    assert state["tenant/call"]["last_error"] == "OperationFailure"
    smb_port.publish.assert_awaited_once()
    serialized_state = json.dumps(state)
    assert "connection-sentinel" not in caplog.text
    assert "credential-sentinel" not in caplog.text
    assert "connection-sentinel" not in serialized_state
    assert "credential-sentinel" not in serialized_state
