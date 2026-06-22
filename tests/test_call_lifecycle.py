import pytest
from unittest.mock import AsyncMock, patch
from src.telephony.esl_client import ESLClient
from src.audio.ingestor import audio_ingestor, AudioChunk


@pytest.mark.asyncio
async def test_channel_answer_creates_call_row():
    client = ESLClient()
    event = {
        "Caller-Unique-ID": "call-abc",
        "variable_zenith_tenant_id": "tenant-1",
        "variable_zenith_pbx_id": "pbx-1",
        "variable_zenith_agent_extension": "4001",
    }

    with patch("src.telephony.esl_client.create_call_record", new=AsyncMock()) as mock_create:
        await client._handle_channel_answer(event)

    mock_create.assert_awaited_once_with("tenant-1", "call-abc", "pbx-1", "4001")


@pytest.mark.asyncio
async def test_channel_hangup_finalizes_call():
    client = ESLClient()
    event = {"Caller-Unique-ID": "call-xyz", "variable_zenith_tenant_id": "tenant-1"}

    with patch("src.telephony.esl_client.finalize_call_record", new=AsyncMock()) as mock_finalize, \
         patch("src.telephony.esl_client.enqueue_recording_upload", new=AsyncMock()):
        await client._handle_channel_hangup(event)

    mock_finalize.assert_awaited_once_with("tenant-1", "call-xyz")


@pytest.mark.asyncio
async def test_channel_hangup_triggers_recording_flush():
    audio_ingestor.buffers["call-flush"] = [
        AudioChunk("call-flush", "tx", b"\x01\x02", 0.0),
        AudioChunk("call-flush", "rx", b"\x03\x04", 0.0),
        AudioChunk("call-flush", "tx", b"\x05\x06", 0.0),
    ]
    client = ESLClient()
    event = {"Caller-Unique-ID": "call-flush", "variable_zenith_tenant_id": "tenant-1"}

    with patch("src.telephony.esl_client.finalize_call_record", new=AsyncMock()), \
         patch("src.telephony.esl_client.enqueue_recording_upload", new=AsyncMock()) as mock_enqueue:
        await client._handle_channel_hangup(event)

    assert "call-flush" not in audio_ingestor.buffers
    mock_enqueue.assert_awaited_once()
    tenant_id, call_id, recordings = mock_enqueue.call_args.args
    assert tenant_id == "tenant-1"
    assert call_id == "call-flush"
    by_channel = {r["channel"]: r["data"] for r in recordings}
    assert by_channel["tx"] == b"\x01\x02\x05\x06"
    assert by_channel["rx"] == b"\x03\x04"
