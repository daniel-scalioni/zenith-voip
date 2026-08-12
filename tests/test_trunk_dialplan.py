import xml.etree.ElementTree as ET
from pathlib import Path

DIALPLAN_PATH = Path(__file__).parents[1] / "freeswitch/conf/dialplan/default.xml"


def _zenith_audio_fork_extension() -> ET.Element:
    tree = ET.parse(DIALPLAN_PATH)
    for extension in tree.getroot().iter("extension"):
        if extension.get("name") == "zenith_audio_fork":
            return extension
    raise AssertionError("extensão zenith_audio_fork não encontrada no dialplan")


def _bridge_action(extension: ET.Element) -> ET.Element:
    for condition in extension.findall("condition"):
        for action in condition.findall("action"):
            if action.get("application") == "bridge":
                return action
    raise AssertionError("nenhuma action bridge encontrada em zenith_audio_fork")


def test_dialplan_preserves_destination_and_bridge_target():
    # Arrange
    extension = _zenith_audio_fork_extension()

    # Act
    bridge_action = _bridge_action(extension)

    # Assert
    assert "/${destination_number}" in bridge_action.get("data", "")
    assert "regex" not in bridge_action.get("data", "").lower()


def test_dialplan_first_condition_no_longer_sets_tenant_context_unconditionally():
    # Arrange
    extension = _zenith_audio_fork_extension()
    first_condition = extension.findall("condition")[0]

    # Act
    set_targets = [
        action.get("data", "") for action in first_condition.findall("action")
        if action.get("application") == "set"
    ]

    # Assert: zenith_call_id/zenith_agent_extension continuam incondicionais,
    # mas zenith_tenant_id/zenith_pbx_id não podem voltar a ser setados aqui —
    # isso reintroduziria a atribuição incondicional que sobrescrevia o
    # contexto injetado pelo diretório para troncos (regressão original da T037
    # era a ausência total; a regressão oposta seria voltar sem guarda).
    assert any(item.startswith("zenith_call_id=") for item in set_targets)
    assert any(item.startswith("zenith_agent_extension=") for item in set_targets)
    assert not any(item.startswith("zenith_tenant_id=") for item in set_targets)
    assert not any(item.startswith("zenith_pbx_id=") for item in set_targets)


def test_dialplan_applies_tenant_fallback_only_when_channel_context_is_empty():
    # Arrange
    extension = _zenith_audio_fork_extension()

    # Act
    guard_condition = next(
        (c for c in extension.findall("condition") if c.get("field") == "${zenith_tenant_id}"),
        None,
    )

    # Assert
    assert guard_condition is not None, "condição de guarda sobre ${zenith_tenant_id} ausente"
    assert guard_condition.get("expression") == "^$"
    set_targets = [
        action.get("data", "") for action in guard_condition.findall("action")
        if action.get("application") == "set"
    ]
    assert "zenith_tenant_id=$${tenant_id}" in set_targets
    assert "zenith_pbx_id=$${pbx_id}" in set_targets


def test_dialplan_guard_never_aborts_the_call_when_tenant_already_set():
    # Arrange
    extension = _zenith_audio_fork_extension()
    guard_condition = next(
        c for c in extension.findall("condition") if c.get("field") == "${zenith_tenant_id}"
    )

    # Act
    break_mode = guard_condition.get("break")

    # Assert: sem break="never", quando zenith_tenant_id já vem setado por um
    # tronco (não casa "^$"), o FreeSWITCH aborta o resto da extensão e a
    # chamada nunca chega em answer/bridge.
    assert break_mode == "never"


def test_dialplan_guard_runs_before_answer_and_bridge():
    # Arrange
    extension = _zenith_audio_fork_extension()
    conditions = extension.findall("condition")

    # Act
    guard_index = next(
        i for i, c in enumerate(conditions) if c.get("field") == "${zenith_tenant_id}"
    )
    bridge_index = next(
        i for i, c in enumerate(conditions)
        if any(a.get("application") == "bridge" for a in c.findall("action"))
    )

    # Assert
    assert guard_index < bridge_index
