import pytest
from unittest.mock import AsyncMock, Mock

from src.telephony import esl_client


@pytest.mark.asyncio
async def test_start_audio_capture_uses_numeric_16000(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    client.send_bgapi = AsyncMock(return_value="+OK")

    # Act
    await client._start_audio_capture("call-16k")

    # Assert
    command = client.send_bgapi.await_args.args[0]
    assert " stereo 16000 " in command
    assert " 8k " not in command


@pytest.mark.asyncio
async def test_channel_answer_forwards_present_caller_and_destination(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    create = AsyncMock()
    monkeypatch.setattr(esl_client, "create_call_record", create)
    monkeypatch.setattr(esl_client, "mark_call_in_progress", AsyncMock(return_value=False))
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
    monkeypatch.setattr(esl_client, "mark_call_in_progress", AsyncMock(return_value=False))
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
    monkeypatch.setattr(esl_client, "mark_call_in_progress", AsyncMock(return_value=False))
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
    monkeypatch.setattr(esl_client, "mark_call_in_progress", AsyncMock(return_value=False))
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
    monkeypatch.setattr(esl_client, "mark_call_in_progress", AsyncMock(return_value=False))
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
async def test_channel_answer_promotes_ringing_record_instead_of_creating(monkeypatch):
    # Arrange: GAP-RE-02 — linha já criada em `ringing` no CHANNEL_CREATE deve ser
    # promovida, não duplicada por um segundo INSERT
    client = esl_client.ESLClient()
    create = AsyncMock()
    mark_in_progress = AsyncMock(return_value=True)
    monkeypatch.setattr(esl_client, "create_call_record", create)
    monkeypatch.setattr(esl_client, "mark_call_in_progress", mark_in_progress)
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
    mark_in_progress.assert_awaited_once_with("tenant", "call")
    create.assert_not_awaited()


# --- CHANNEL_ANSWER conta/loga chamada perdida por falta de tenant_id (fix GAP-RE-03) ---


@pytest.mark.asyncio
async def test_channel_answer_increments_dropped_metric_for_inbound_leg_without_tenant(monkeypatch):
    # Arrange: perna A (inbound) real, sem tenant_id — perda silenciosa que o GAP-RE-03
    # reclamava não ter métrica nem log
    client = esl_client.ESLClient()
    from src.utils import telemetry

    counter = Mock()
    monkeypatch.setattr(telemetry.call_dropped_no_tenant_total, "inc", counter)
    event = {
        "Caller-Unique-ID": "call",
        "Call-Direction": "inbound",
        "Caller-Caller-ID-Number": "1001",
        "Caller-Destination-Number": "1002",
    }

    # Act
    await client._handle_channel_answer(event)

    # Assert
    counter.assert_called_once()


@pytest.mark.asyncio
async def test_channel_answer_does_not_increment_dropped_metric_for_outbound_leg(monkeypatch):
    # Arrange: regressão — a perna B de toda chamada bridgeada também não tem tenant_id
    # no ANSWER (comportamento esperado, não um drop real); sem o filtro de direção, a
    # métrica dispararia em 100% das chamadas bridgeadas, virando ruído inútil
    client = esl_client.ESLClient()
    from src.utils import telemetry

    counter = Mock()
    monkeypatch.setattr(telemetry.call_dropped_no_tenant_total, "inc", counter)
    event = {
        "Caller-Unique-ID": "b-leg-call",
        "Call-Direction": "outbound",
        "Other-Leg-Unique-ID": "a-leg-call",
        "Caller-Destination-Number": "3101001",
    }

    # Act
    await client._handle_channel_answer(event)

    # Assert
    counter.assert_not_called()


@pytest.mark.asyncio
async def test_channel_answer_does_not_increment_dropped_metric_when_tenant_present(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    monkeypatch.setattr(esl_client, "create_call_record", AsyncMock())
    monkeypatch.setattr(esl_client, "mark_call_in_progress", AsyncMock(return_value=False))
    monkeypatch.setattr(client, "_start_audio_capture", AsyncMock())
    from src.utils import telemetry

    counter = Mock()
    monkeypatch.setattr(telemetry.call_dropped_no_tenant_total, "inc", counter)
    event = {
        "Caller-Unique-ID": "call",
        "Call-Direction": "inbound",
        "variable_zenith_tenant_id": "tenant",
        "variable_zenith_pbx_id": "pbx",
    }

    # Act
    await client._handle_channel_answer(event)

    # Assert
    counter.assert_not_called()


# --- CHANNEL_CREATE cria a linha ringing (fix GAP-RE-02) ---


@pytest.mark.asyncio
async def test_channel_create_creates_ringing_record_when_trunk_tenant_already_injected(monkeypatch):
    # Arrange: tronco ATA já chega com zenith_tenant_id injetado pelo diretório dinâmico
    client = esl_client.ESLClient()
    create_ringing = AsyncMock()
    monkeypatch.setattr(esl_client, "create_ringing_call_record", create_ringing)
    event = {
        "Caller-Unique-ID": "call",
        "Call-Direction": "inbound",
        "variable_zenith_tenant_id": "condominio-parque-portugal",
        "variable_zenith_pbx_id": "pbx-parque-portugal",
        "Caller-Caller-ID-Number": "55119999",
        "Caller-Destination-Number": "2099",
    }

    # Act
    await client._handle_channel_create(event)

    # Assert
    create_ringing.assert_awaited_once_with(
        "condominio-parque-portugal", "call", "pbx-parque-portugal", "", "55119999", "2099"
    )


@pytest.mark.asyncio
async def test_channel_create_uses_variable_zenith_agent_extension_over_sip_from_user(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    create_ringing = AsyncMock()
    monkeypatch.setattr(esl_client, "create_ringing_call_record", create_ringing)
    event = {
        "Caller-Unique-ID": "call",
        "Call-Direction": "inbound",
        "variable_zenith_tenant_id": "tenant",
        "variable_zenith_pbx_id": "pbx",
        "variable_zenith_agent_extension": "1001",
        "variable_sip_from_user": "should-be-ignored",
    }

    # Act
    await client._handle_channel_create(event)

    # Assert
    assert create_ringing.await_args.args[3] == "1001"


@pytest.mark.asyncio
async def test_channel_create_skips_ringing_record_when_tenant_absent(monkeypatch):
    # Arrange: sem variable_zenith_tenant_id no evento — sem fallback global (removido:
    # criava linha ringing que ANSWER/HANGUP nunca conseguiriam encontrar de volta, já que
    # local_extension/echo_test nunca setam zenith_* em lugar nenhum do ciclo de vida)
    client = esl_client.ESLClient()
    create_ringing = AsyncMock()
    monkeypatch.setattr(esl_client, "create_ringing_call_record", create_ringing)
    event = {"Caller-Unique-ID": "call", "Call-Direction": "inbound"}

    # Act
    await client._handle_channel_create(event)

    # Assert
    create_ringing.assert_not_awaited()


@pytest.mark.asyncio
async def test_channel_create_skips_ringing_record_for_outbound_leg(monkeypatch):
    # Arrange: regressão real (2026-08-21) — CHANNEL_CREATE dispara para as duas pernas de
    # toda chamada bridgeada (GAP-ESL-08). A perna B (Call-Direction=outbound, criada pelo
    # FreeSWITCH ao originar o bridge) nunca carrega tenant_id de verdade, nem no ANSWER
    # (confirmado com evento real do FreeSWITCH). Mesmo que ela viesse com
    # variable_zenith_tenant_id (não deveria, mas por defesa em profundidade), o guard de
    # direção barra antes de chegar lá.
    client = esl_client.ESLClient()
    create_ringing = AsyncMock()
    monkeypatch.setattr(esl_client, "create_ringing_call_record", create_ringing)
    event = {
        "Caller-Unique-ID": "b-leg-call",
        "Call-Direction": "outbound",
        "Other-Leg-Unique-ID": "a-leg-call",
        "variable_zenith_tenant_id": "akom",
        "Caller-Destination-Number": "3101001",
    }

    # Act
    await client._handle_channel_create(event)

    # Assert
    create_ringing.assert_not_awaited()


@pytest.mark.asyncio
async def test_channel_create_skips_ringing_record_for_local_extension_without_zenith_vars(monkeypatch):
    # Arrange: mesmo depois do fix do GAP-RE-03 (2026-08-24, extension zenith_call_context),
    # CHANNEL_CREATE continua sem variable_zenith_tenant_id para ramal local — a extension seta
    # via `set` no dialplan, que só executa DEPOIS do CREATE disparar. ANSWER/HANGUP já carregam
    # a variável (dialplan já rodou por completo a essa altura); só o estado `ringing`
    # intermediário não existe pra esse caminho — cai direto em `create_call_record` no ANSWER.
    # Criar `ringing` aqui via fallback deixaria a linha órfã para sempre, já que nada depois
    # consegue encontrá-la de volta no mesmo call_id antes do dialplan terminar
    client = esl_client.ESLClient()
    create_ringing = AsyncMock()
    monkeypatch.setattr(esl_client, "create_ringing_call_record", create_ringing)
    event = {
        "Caller-Unique-ID": "call",
        "Call-Direction": "inbound",
        "Caller-Caller-ID-Number": "1001",
        "Caller-Destination-Number": "1002",
    }

    # Act
    await client._handle_channel_create(event)

    # Assert
    create_ringing.assert_not_awaited()


@pytest.mark.asyncio
async def test_channel_create_skips_ringing_record_for_manual_linkage(monkeypatch):
    # Arrange: *88 é sinal interno, nunca gera linha Call
    client = esl_client.ESLClient()
    create_ringing = AsyncMock()
    monkeypatch.setattr(esl_client, "create_ringing_call_record", create_ringing)
    monkeypatch.setattr(client, "_handle_manual_linkage", AsyncMock())
    event = {"Caller-Unique-ID": "call", "Caller-Destination-Number": "*88"}

    # Act
    await client._handle_channel_create(event)

    # Assert
    create_ringing.assert_not_awaited()


# --- CHANNEL_HANGUP classifica Hangup-Cause (fix GAP-RE-02) ---


@pytest.mark.asyncio
async def test_channel_hangup_forwards_hangup_cause_to_finalize(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    finalize = AsyncMock()
    monkeypatch.setattr(esl_client, "finalize_call_record", finalize)
    monkeypatch.setattr(client, "_track_trunk_call", AsyncMock())
    from src.audio.ingestor import audio_ingestor
    monkeypatch.setattr(audio_ingestor, "finalize_stream", AsyncMock())
    event = {
        "Caller-Unique-ID": "call",
        "variable_zenith_tenant_id": "tenant",
        "Hangup-Cause": "USER_BUSY",
    }

    # Act
    await client._handle_channel_hangup(event)

    # Assert
    finalize.assert_awaited_once_with("tenant", "call", "USER_BUSY")


@pytest.mark.asyncio
async def test_channel_hangup_passes_none_when_hangup_cause_absent(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    finalize = AsyncMock()
    monkeypatch.setattr(esl_client, "finalize_call_record", finalize)
    monkeypatch.setattr(client, "_track_trunk_call", AsyncMock())
    from src.audio.ingestor import audio_ingestor
    monkeypatch.setattr(audio_ingestor, "finalize_stream", AsyncMock())
    event = {"Caller-Unique-ID": "call", "variable_zenith_tenant_id": "tenant"}

    # Act
    await client._handle_channel_hangup(event)

    # Assert
    finalize.assert_awaited_once_with("tenant", "call", None)


@pytest.mark.asyncio
async def test_channel_hangup_skips_finalize_when_tenant_context_absent(monkeypatch):
    # Arrange
    client = esl_client.ESLClient()
    finalize = AsyncMock()
    monkeypatch.setattr(esl_client, "finalize_call_record", finalize)
    monkeypatch.setattr(client, "_track_trunk_call", AsyncMock())
    from src.audio.ingestor import audio_ingestor
    monkeypatch.setattr(audio_ingestor, "finalize_stream", AsyncMock())
    event = {"Caller-Unique-ID": "call", "Hangup-Cause": "NORMAL_CLEARING"}

    # Act
    await client._handle_channel_hangup(event)

    # Assert
    finalize.assert_not_awaited()


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
