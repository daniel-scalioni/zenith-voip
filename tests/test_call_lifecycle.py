import pytest
from unittest.mock import AsyncMock, patch

from src.telephony.esl_client import ESLClient


@pytest.mark.asyncio
async def test_channel_answer_creates_call_row():
    # Arrange
    client = ESLClient()
    event = {
        "Caller-Unique-ID": "call-abc",
        "variable_zenith_tenant_id": "tenant-1",
        "variable_zenith_pbx_id": "pbx-1",
        "variable_zenith_agent_extension": "4001",
    }

    # Act
    with patch("src.telephony.esl_client.create_call_record", new=AsyncMock()) as create, patch.object(
        client, "_start_audio_capture", new=AsyncMock()
    ):
        await client._handle_channel_answer(event)

    # Assert
    create.assert_awaited_once_with("tenant-1", "call-abc", "pbx-1", "4001")


@pytest.mark.asyncio
async def test_channel_hangup_finalizes_call_and_recording_once():
    # Arrange
    client = ESLClient()
    event = {"Caller-Unique-ID": "call-xyz", "variable_zenith_tenant_id": "tenant-1"}

    # Act
    with patch("src.telephony.esl_client.finalize_call_record", new=AsyncMock()) as finalize, patch(
        "src.audio.ingestor.audio_ingestor.finalize_stream", new=AsyncMock(return_value=True)
    ) as finalize_stream:
        await client._handle_channel_hangup(event)

    # Assert
    finalize.assert_awaited_once_with("tenant-1", "call-xyz")
    finalize_stream.assert_awaited_once_with("call-xyz")
