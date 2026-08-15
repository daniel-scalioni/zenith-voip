from types import SimpleNamespace

import pytest

from src.audio.capacity import RecordingCapacityGuard


@pytest.mark.asyncio
async def test_capacity_reserves_30_five_minute_calls_with_headroom(monkeypatch, tmp_path):
    # Arrange
    total = 2 * 1024**3
    monkeypatch.setattr("src.audio.capacity.shutil.disk_usage", lambda _p: SimpleNamespace(total=total, used=0, free=total))
    guard = RecordingCapacityGuard(tmp_path)

    # Act
    accepted = [await guard.reserve(f"call-{i}") for i in range(30)]

    # Assert
    assert all(accepted)
    assert guard.reserved_bytes == 30 * 19_200_000


@pytest.mark.asyncio
async def test_capacity_hysteresis_refuses_below_20_and_resumes_at_30(monkeypatch, tmp_path):
    # Arrange
    total = 2 * 1024**3
    usage = {"used": int(total * 0.80)}
    monkeypatch.setattr("src.audio.capacity.shutil.disk_usage", lambda _p: SimpleNamespace(total=total, used=usage["used"], free=total-usage["used"]))
    guard = RecordingCapacityGuard(tmp_path, headroom_bytes=0)

    # Act / Assert
    assert not await guard.reserve("blocked")
    assert guard.degraded
    usage["used"] = int(total * 0.71)
    assert not await guard.reserve("still-blocked")
    usage["used"] = int(total * 0.69)
    assert await guard.reserve("accepted")
    assert not guard.degraded
    assert await guard.release("accepted")
    assert not await guard.release("accepted")


@pytest.mark.asyncio
async def test_capacity_counts_only_remaining_bytes_of_active_recording(monkeypatch, tmp_path):
    # Arrange
    total = 1_000_000_000
    call_dir = tmp_path / "tenant" / "call"
    call_dir.mkdir(parents=True)
    monkeypatch.setattr("src.audio.capacity.shutil.disk_usage", lambda _p: SimpleNamespace(total=total, used=10_000_000, free=990_000_000))
    guard = RecordingCapacityGuard(tmp_path, max_call_seconds=10, headroom_bytes=0)
    assert await guard.reserve("call")
    (call_dir / "tx.tmp.raw").write_bytes(b"x" * 1000)

    # Act
    remaining = guard.remaining_reserved_bytes

    # Assert
    assert remaining == guard.bytes_per_call - 1000


@pytest.mark.asyncio
async def test_capacity_reserves_space_for_pending_raw_to_wav_expansion(monkeypatch, tmp_path):
    # Arrange
    total = 2 * 1024**3
    raw_size = 19_200_000
    call_dir = tmp_path / "tenant" / "old-call"
    call_dir.mkdir(parents=True)
    with (call_dir / "tx.raw").open("wb") as raw:
        raw.truncate(raw_size)
    with (call_dir / "tx.tmp.wav").open("wb") as temporary:
        temporary.truncate(5_000_000)
    monkeypatch.setattr(
        "src.audio.capacity.shutil.disk_usage",
        lambda _p: SimpleNamespace(total=total, used=raw_size + 5_000_000, free=total - raw_size - 5_000_000),
    )
    guard = RecordingCapacityGuard(tmp_path, headroom_bytes=0)

    # Act
    pending = guard.pending_processing_bytes

    # Assert: só o crescimento ainda não materializado do WAV entra na projeção.
    assert pending == raw_size - 5_000_000
