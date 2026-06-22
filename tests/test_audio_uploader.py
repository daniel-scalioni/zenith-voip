import os
import pytest
from unittest.mock import patch
from src.workers.audio_uploader import upload_audio_chunk, upload_recording_batch


@pytest.mark.asyncio
async def test_upload_audio_chunk_writes_to_local_path(tmp_path):
    with patch("src.workers.audio_uploader.settings.RECORDINGS_PATH", str(tmp_path)):
        result = await upload_audio_chunk(
            None, tenant_id="tenant-1", call_id="call-001", channel="tx", audio_data=b"\x00\x01"
        )

    expected_path = tmp_path / "tenant-1" / "call-001" / "tx.raw"
    assert result["status"] == "uploaded"
    assert result["path"] == str(expected_path)
    assert expected_path.read_bytes() == b"\x00\x01"


@pytest.mark.asyncio
async def test_upload_recording_batch_dispatches_both_channels(tmp_path):
    with patch("src.workers.audio_uploader.settings.RECORDINGS_PATH", str(tmp_path)):
        results = await upload_recording_batch(
            None,
            tenant_id="tenant-1",
            call_id="call-001",
            recordings=[
                {"channel": "tx", "data": b"\x01\x02"},
                {"channel": "rx", "data": b"\x03\x04"},
            ],
        )

    assert len(results) == 2
    assert all(r["status"] == "uploaded" for r in results)
    call_dir = tmp_path / "tenant-1" / "call-001"
    assert (call_dir / "tx.raw").read_bytes() == b"\x01\x02"
    assert (call_dir / "rx.raw").read_bytes() == b"\x03\x04"
