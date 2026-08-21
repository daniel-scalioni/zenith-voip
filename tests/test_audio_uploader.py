from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.workers import audio_uploader


@pytest.mark.asyncio
async def test_upload_batch_converts_both_final_channels(tmp_path, monkeypatch):
    # Arrange
    call_dir = tmp_path / "tenant-1" / "call-001"
    call_dir.mkdir(parents=True)
    (call_dir / "tx.raw").write_bytes(b"tx")
    (call_dir / "rx.raw").write_bytes(b"rx")

    async def convert(raw_path):
        wav = Path(raw_path).with_suffix(".wav")
        wav.write_bytes(b"wav")
        return str(wav)

    monkeypatch.setattr(audio_uploader, "_convert_to_wav", convert)

    # Act
    with patch("src.workers.audio_uploader.settings.RECORDINGS_PATH", str(tmp_path)):
        results = await audio_uploader.upload_recording_batch(None, "tenant-1", "call-001")

    # Assert
    assert len(results) == 2
    assert all(item["status"] == "uploaded" for item in results)
    assert (call_dir / "tx.raw").exists()
    assert (call_dir / "rx.raw").exists()
