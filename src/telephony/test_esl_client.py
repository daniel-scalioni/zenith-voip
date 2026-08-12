import pytest
from unittest.mock import AsyncMock, Mock

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


@pytest.mark.asyncio
async def test_channel_answer_skips_call_creation_when_tenant_context_absent(monkeypatch):
    # Arrange: regressão real da feature 012 (T037, 2026-08-05 a 2026-08-12) — o dialplan
    # deixou de propagar zenith_tenant_id/zenith_pbx_id para ramal legado, e toda chamada
    # de ramal comum passava por aqui sem a variável, perdendo a linha Call em silêncio.
    client = esl_client.ESLClient()
    create = AsyncMock()
    monkeypatch.setattr(esl_client, "create_call_record", create)
    monkeypatch.setattr(client, "_start_audio_capture", AsyncMock())
    event = {
        "Caller-Unique-ID": "call",
        "variable_zenith_agent_extension": "1001",
        "Caller-Caller-ID-Number": "55119999",
        "Caller-Destination-Number": "2099",
    }

    # Act
    await client._handle_channel_answer(event)

    # Assert
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_channel_answer_creates_call_for_legacy_extension_using_fallback_tenant(monkeypatch):
    # Arrange: pós-fix (T058) — ramal legado sem identidade de tronco recebe o fallback
    # global do dialplan (zenith_tenant_id=$${tenant_id}), que hoje resolve para "akom".
    client = esl_client.ESLClient()
    create = AsyncMock()
    monkeypatch.setattr(esl_client, "create_call_record", create)
    monkeypatch.setattr(client, "_start_audio_capture", AsyncMock())
    event = {
        "Caller-Unique-ID": "call",
        "variable_zenith_tenant_id": "akom",
        "variable_zenith_pbx_id": "pbx-akom",
        "variable_zenith_agent_extension": "1001",
        "Caller-Caller-ID-Number": "55119999",
        "Caller-Destination-Number": "2099",
    }

    # Act
    await client._handle_channel_answer(event)

    # Assert
    create.assert_awaited_once_with("akom", "call", "pbx-akom", "1001", "55119999", "2099")


@pytest.mark.asyncio
async def test_channel_answer_creates_call_for_trunk_using_directory_tenant_not_global_fallback(monkeypatch):
    # Arrange: tronco ATA resolvido via mod_xml_curl (src/api/freeswitch_directory.py) chega
    # com zenith_tenant_id já definido pelo diretório — precisa criar a Call com o tenant do
    # tronco, nunca com o fallback global "akom" (a guarda do dialplan, T058, garante isso
    # antes do evento chegar aqui; este teste prova a consequência no nível de serviço).
    client = esl_client.ESLClient()
    create = AsyncMock()
    monkeypatch.setattr(esl_client, "create_call_record", create)
    monkeypatch.setattr(client, "_start_audio_capture", AsyncMock())
    event = {
        "Caller-Unique-ID": "call",
        "variable_zenith_tenant_id": "condominio-parque-portugal",
        "variable_zenith_pbx_id": "pbx-parque-portugal",
        "variable_zenith_agent_extension": "1001",
        "Caller-Caller-ID-Number": "55119999",
        "Caller-Destination-Number": "2099",
    }

    # Act
    await client._handle_channel_answer(event)

    # Assert
    create.assert_awaited_once_with(
        "condominio-parque-portugal", "call", "pbx-parque-portugal", "1001", "55119999", "2099"
    )
    assert create.await_args.args[0] != "akom"


@pytest.mark.asyncio
async def test_connect_subscribes_custom_sofia_events_without_second_listener(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    reader = AsyncMock()
    reader.read.side_effect = [b"Content-Type: auth/request\n\n", b"+OK accepted\n\n"]
    writer = Mock()
    writer.drain = AsyncMock()
    monkeypatch.setattr(esl_client.asyncio, "open_connection", AsyncMock(return_value=(reader, writer)))
    monkeypatch.setattr(client, "_reconcile_trunks", AsyncMock())

    # Act
    await client.connect()

    # Assert
    subscription = b"".join(call.args[0] for call in writer.write.call_args_list)
    assert b"CUSTOM sofia::register sofia::unregister sofia::expire" in subscription
    client._reconcile_trunks.assert_awaited_once()


@pytest.mark.asyncio
async def test_custom_sofia_event_isolated_from_following_events(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    handler = AsyncMock()
    monkeypatch.setattr(client, "_handle_trunk_registration", handler)
    event = {"Event-Name": "CUSTOM", "Event-Subclass": "sofia::expire"}

    # Act
    await client._process_event(esl_client.json.dumps(event))

    # Assert
    handler.assert_awaited_once_with(event)
