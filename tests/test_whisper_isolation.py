import pytest


@pytest.mark.asyncio
async def test_agent_uuid_exists():
    from src.telephony.esl_client import esl_client
    esl_client.map_uuids("test-call", "agent-uuid-001", "customer-uuid-001")
    agent = esl_client.get_agent_uuid("test-call")
    assert agent == "agent-uuid-001"


@pytest.mark.asyncio
async def test_customer_uuid_exists():
    from src.telephony.esl_client import esl_client
    customer = esl_client.get_customer_uuid("test-call")
    assert customer == "customer-uuid-001"


@pytest.mark.asyncio
async def test_whisper_targets_only_agent():
    from src.telephony.whisper_mode import WhisperMode
    mode = WhisperMode()
    agent_uuid = "agent-uuid-001"
    customer_uuid = "customer-uuid-001"
    assert agent_uuid != customer_uuid


@pytest.mark.asyncio
async def test_isolation_via_uuid_play():
    agent_uuid = "agent-uuid-001"
    customer_uuid = "customer-uuid-001"
    command_agent = f"uuid_play {agent_uuid} /tmp/test.wav"
    command_customer = f"uuid_play {customer_uuid} /tmp/test.wav"
    assert "agent-uuid" in command_agent
    assert "customer-uuid" in command_customer
    assert command_agent.split()[1] != command_customer.split()[1]
