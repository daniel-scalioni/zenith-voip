"""Contrato do dialplan para GAP-RE-03: ramal local (condomínio) também popula zenith_*."""
import xml.etree.ElementTree as ET
from pathlib import Path

DIALPLAN_PATH = Path(__file__).parents[1] / "freeswitch/conf/dialplan/default.xml"


def _load_extensions() -> list[ET.Element]:
    tree = ET.parse(DIALPLAN_PATH)
    return list(tree.getroot().iter("extension"))


def _extension(name: str) -> ET.Element:
    for extension in _load_extensions():
        if extension.get("name") == name:
            return extension
    raise AssertionError(f"extensão {name} não encontrada no dialplan")


def test_zenith_call_context_has_continue_true():
    # Arrange / Act
    extension = _extension("zenith_call_context")

    # Assert: sem continue="true", o dialplan pararia aqui e local_extension nunca rodaria
    assert extension.get("continue") == "true"


def test_zenith_call_context_does_not_answer_or_bridge():
    # Arrange
    extension = _extension("zenith_call_context")

    # Act
    applications = {
        action.get("application")
        for condition in extension.findall("condition")
        for action in condition.findall("action")
    }

    # Assert: só popula variável, não consome a chamada — quem bridgeia é
    # local_extension (condomínio) ou zenith_audio_fork (tronco), não esta extension
    assert applications == {"set"}


def test_zenith_call_context_sets_call_id_and_agent_extension_unconditionally():
    # Arrange
    extension = _extension("zenith_call_context")
    first_condition = extension.findall("condition")[0]

    # Act
    set_targets = [
        action.get("data", "") for action in first_condition.findall("action")
        if action.get("application") == "set"
    ]

    # Assert
    assert any(item.startswith("zenith_call_id=") for item in set_targets)
    assert any(item.startswith("zenith_agent_extension=") for item in set_targets)


def test_zenith_call_context_applies_tenant_fallback_only_when_channel_context_is_empty():
    # Arrange
    extension = _extension("zenith_call_context")

    # Act
    guard_condition = next(
        (c for c in extension.findall("condition") if c.get("field") == "${zenith_tenant_id}"),
        None,
    )

    # Assert: mesma guarda de zenith_audio_fork — nunca sobrescreve tenant_id já
    # injetado por um tronco (mod_xml_curl)
    assert guard_condition is not None, "condição de guarda sobre ${zenith_tenant_id} ausente"
    assert guard_condition.get("expression") == "^$"
    assert guard_condition.get("break") == "never"
    set_targets = [
        action.get("data", "") for action in guard_condition.findall("action")
        if action.get("application") == "set"
    ]
    assert "zenith_tenant_id=$${tenant_id}" in set_targets
    assert "zenith_pbx_id=$${pbx_id}" in set_targets


def test_zenith_call_context_never_sets_tenant_id_unguarded():
    # Arrange
    extension = _extension("zenith_call_context")

    # Act: toda condition que NÃO é a guarda ${zenith_tenant_id}="^$"
    other_conditions = [
        c for c in extension.findall("condition")
        if not (c.get("field") == "${zenith_tenant_id}" and c.get("expression") == "^$")
    ]
    leaked_sets = [
        action.get("data", "")
        for condition in other_conditions
        for action in condition.findall("action")
        if action.get("application") == "set"
        and action.get("data", "").startswith(("zenith_tenant_id=", "zenith_pbx_id="))
    ]

    # Assert: regressão W008 (_reversa_forward/012-trunk-registration/regression-watch.md) —
    # setar zenith_tenant_id fora da guarda cruzaria identidade entre tenants (todo tronco
    # reportaria tenant_id=akom). A guarda em si já é testada acima; isto garante que nenhuma
    # OUTRA condition desta extension também seta essas duas variáveis
    assert leaked_sets == []


def test_zenith_call_context_runs_before_local_extension():
    # Arrange
    extensions = _load_extensions()
    names = [e.get("name") for e in extensions]

    # Act / Assert: bridge é bloqueante — se a ordem for invertida, as variáveis
    # só seriam setadas depois do bridge retornar, tarde demais para o guard do
    # CHANNEL_ANSWER em esl_client.py (achado do /brainstorming-multiagent, PR #12)
    assert names.index("zenith_call_context") < names.index("local_extension")


def test_local_extension_itself_unchanged_no_continue_no_extra_actions():
    # Arrange
    extension = _extension("local_extension")

    # Act
    applications = [
        action.get("application")
        for condition in extension.findall("condition")
        for action in condition.findall("action")
    ]

    # Assert: local_extension continua só bridgeando — não ganhou continue="true"
    # nem sets duplicados; toda a lógica de variável fica isolada em
    # zenith_call_context, que já rodou antes
    assert extension.get("continue") is None
    assert applications == ["bridge"]


def test_local_extension_bridge_target_unchanged():
    # Arrange
    extension = _extension("local_extension")
    bridge_action = extension.find("condition/action[@application='bridge']")

    # Assert
    assert bridge_action.get("data") == "user/$1@$${domain}"
