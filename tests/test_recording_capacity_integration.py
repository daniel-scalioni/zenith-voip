from types import SimpleNamespace

import pytest

from src.audio.capacity import RecordingCapacityGuard


@pytest.mark.asyncio
async def test_thirty_five_minute_reservations_keep_twenty_percent_free(monkeypatch, tmp_path):
    # Arrange: backlog já materializado mais headroom de conversões, sem alocar 2 GiB reais.
    total = 2 * 1024**3
    backlog = 600 * 1024**2
    monkeypatch.setattr(
        "src.audio.capacity.shutil.disk_usage",
        lambda _path: SimpleNamespace(total=total, used=backlog, free=total - backlog),
    )
    guard = RecordingCapacityGuard(tmp_path)

    # Act
    decisions = [await guard.reserve(f"call-{index}") for index in range(30)]
    projected = backlog + guard.remaining_reserved_bytes + guard.headroom_bytes
    free_percent = 100 * (total - projected) / total

    # Assert
    assert all(decisions)
    assert free_percent >= 20


@pytest.mark.asyncio
async def test_pending_conversion_backlog_reduces_new_admissions_before_twenty_percent(monkeypatch, tmp_path):
    # Arrange: 30 chamadas encerradas deixaram raws aguardando WAV.
    total = 2 * 1024**3
    raw_bytes = 30 * 19_200_000
    call_dir = tmp_path / "tenant" / "backlog"
    call_dir.mkdir(parents=True)
    with (call_dir / "tx.raw").open("wb") as raw:
        raw.truncate(raw_bytes)
    monkeypatch.setattr(
        "src.audio.capacity.shutil.disk_usage",
        lambda _path: SimpleNamespace(total=total, used=raw_bytes, free=total - raw_bytes),
    )
    guard = RecordingCapacityGuard(tmp_path)

    # Act
    accepted = 0
    while await guard.reserve(f"new-{accepted}"):
        accepted += 1
    projected = raw_bytes + guard.pending_processing_bytes + guard.remaining_reserved_bytes + guard.headroom_bytes

    # Assert
    assert accepted < 30
    assert 100 * (total - projected) / total >= 20
