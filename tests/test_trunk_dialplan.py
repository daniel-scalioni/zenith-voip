import re
import xml.etree.ElementTree as ET
from pathlib import Path


DIALPLAN_PATH = Path(__file__).parents[1] / "freeswitch/conf/dialplan/default.xml"


def _dialplan_extensions() -> list[ET.Element]:
    tree = ET.parse(DIALPLAN_PATH)
    return list(tree.getroot().iter("extension"))


def _extension_by_name(name: str) -> ET.Element:
    for extension in _dialplan_extensions():
        if extension.get("name") == name:
            return extension
    raise AssertionError(f"extensão {name} não encontrada no dialplan")


def _destination_expression(extension: ET.Element) -> str:
    for condition in extension.findall("condition"):
        if condition.get("field") == "destination_number":
            return condition.get("expression", "")
    raise AssertionError("condição destination_number não encontrada")


def _first_extension_for_destination(destination: str) -> ET.Element | None:
    for extension in _dialplan_extensions():
        for condition in extension.findall("condition"):
            if condition.get("field") != "destination_number":
                continue
            if re.search(condition.get("expression", ""), destination):
                return extension
    return None


def test_dialplan_routes_every_numeric_destination_through_upstream():
    # Arrange
    destinations = ("1003", "9196", "30001", "1140100", "3101001")
    expected_bridge = (
        "sofia/gateway/upstream-${sip_from_user}/${destination_number}"
    )

    # Act
    matched_extensions = [
        _first_extension_for_destination(destination) for destination in destinations
    ]
    bridge_targets = [
        action.get("data")
        for action in _extension_by_name("zenith_audio_fork").iter("action")
        if action.get("application") == "bridge"
    ]

    # Assert
    assert all(extension is not None for extension in matched_extensions)
    assert all(
        extension.get("name") == "zenith_audio_fork"
        for extension in matched_extensions
    )
    assert bridge_targets == [expected_bridge]


def test_dialplan_has_no_local_user_bridge():
    # Arrange
    extensions = _dialplan_extensions()

    # Act
    extension_names = {extension.get("name") for extension in extensions}
    bridge_targets = [
        action.get("data", "")
        for extension in extensions
        for action in extension.iter("action")
        if action.get("application") == "bridge"
    ]

    # Assert
    assert "local_extension" not in extension_names
    assert not any(target.startswith("user/") for target in bridge_targets)


def test_dialplan_preserves_only_explicit_technical_local_routes():
    # Arrange
    technical_destinations = {
        "*9196": "echo_test",
        "*88": "manual_linkage",
        "play:filler": "playback_filler",
    }

    # Act
    matched_names = {
        destination: _first_extension_for_destination(destination).get("name")
        for destination in technical_destinations
    }

    # Assert
    assert matched_names == technical_destinations


def test_dialplan_upstream_regex_rejects_every_technical_route():
    # Arrange
    technical_destinations = ("*9196", "*88", "play:filler")
    numeric_expression = _destination_expression(
        _extension_by_name("zenith_audio_fork")
    )

    # Act
    upstream_matches = [
        re.search(numeric_expression, destination)
        for destination in technical_destinations
    ]

    # Assert
    assert numeric_expression.startswith("^")
    assert numeric_expression.endswith("$")
    assert upstream_matches == [None, None, None]
