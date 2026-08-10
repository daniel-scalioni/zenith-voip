from pathlib import Path


def test_dialplan_preserves_destination_and_does_not_use_global_tenant_context():
    # Arrange
    text = (Path(__file__).parents[1] / "freeswitch/conf/dialplan/default.xml").read_text(encoding="utf-8")

    # Act
    bridge_lines = [line.strip() for line in text.splitlines() if "application=\"bridge\"" in line]

    # Assert
    assert any("/${destination_number}" in line for line in bridge_lines)
    assert 'zenith_tenant_id=$${tenant_id}' not in text
    assert 'zenith_pbx_id=$${pbx_id}' not in text
    assert "regex" not in " ".join(bridge_lines).lower()
