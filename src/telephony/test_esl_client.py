import pytest
from unittest.mock import AsyncMock

from src.telephony import esl_client


@pytest.mark.asyncio
async def test_channel_answer_forwards_present_caller_and_destination(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    create = AsyncMock()
    monkeypatch.setattr(esl_client, "create_call_record", create)
    monkeypatch.setattr(client, "_start_audio_capture", AsyncMock())
    event = {
        "Caller-Unique-ID": "call",
        "variable_zenith_tenant_id": "tenant",
        "variable_zenith_pbx_id": "pbx",
        "variable_zenith_agent_extension": "1001",
        "Caller-Caller-ID-Number": "55119999",
        "Caller-Destination-Number": "2099",
    }

    # Act
    await client._handle_channel_answer(event)

    # Assert
    create.assert_awaited_once_with("tenant", "call", "pbx", "1001", "55119999", "2099")


@pytest.mark.asyncio
async def test_channel_answer_forwards_none_when_numbers_absent(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    create = AsyncMock()
    monkeypatch.setattr(esl_client, "create_call_record", create)
    monkeypatch.setattr(client, "_start_audio_capture", AsyncMock())
    event = {
        "Caller-Unique-ID": "call",
        "variable_zenith_tenant_id": "tenant",
        "variable_zenith_pbx_id": "pbx",
        "variable_zenith_agent_extension": "1001",
    }

    # Act
    await client._handle_channel_answer(event)

    # Assert
    create.assert_awaited_once_with("tenant", "call", "pbx", "1001")
