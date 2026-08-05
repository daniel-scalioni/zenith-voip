import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def test_xml_curl_is_preloaded_and_example_contains_no_real_secret():
    # Arrange
    modules = ROOT / "freeswitch/conf/autoload_configs/modules.conf.xml"
    example = ROOT / "freeswitch/conf/autoload_configs/xml_curl.conf.xml.example"

    # Act
    modules_text = modules.read_text(encoding="utf-8")
    example_text = example.read_text(encoding="utf-8")

    # Assert
    assert modules_text.index("mod_xml_curl") < modules_text.index("mod_sofia")
    assert not (ROOT / "freeswitch/conf/autoload_configs/pre_load_modules.conf.xml").exists()
    assert "bindings=\"directory\"" in example_text
    assert '<param name="method" value="POST"/>' in example_text
    assert "CHANGE_ME" not in example_text
    assert "gateway-credentials" not in example_text


def test_renderer_writes_private_config_atomically_with_mode_0600(tmp_path):
    # Arrange
    output = tmp_path / "xml_curl.conf.xml"
    env = os.environ.copy()
    env.update({
        "FREESWITCH_DIRECTORY_BASIC_USERNAME": "fixture-user",
        "FREESWITCH_DIRECTORY_BASIC_PASSWORD": "fixture-canary-secret",
        "FREESWITCH_DIRECTORY_URL": "http://127.0.0.1:8001/internal/freeswitch/directory",
    })

    # Act
    result = subprocess.run(
        [sys.executable, "scripts/render_freeswitch_secrets.py", "--output", str(output)],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )

    # Assert
    assert result.returncode == 0
    assert output.stat().st_mode & 0o777 == 0o600
    assert not output.with_suffix(".tmp").exists()
    assert '<param name="method" value="POST"' in output.read_text(encoding="utf-8")
    assert "fixture-canary-secret" not in result.stdout + result.stderr


def test_only_profiles_5060_and_7060_reference_authenticated_directory():
    # Arrange
    profiles = {
        name: (ROOT / f"freeswitch/conf/sip_profiles/{name}.xml").read_text(encoding="utf-8")
        for name in ("internal", "internal-7060", "internal-5062")
    }

    # Act
    target_auth = {name: "accept-blind-reg\" value=\"false" in text for name, text in profiles.items()}

    # Assert
    assert target_auth["internal"] is True
    assert target_auth["internal-7060"] is True
    assert target_auth["internal-5062"] is False
    assert 'accept-blind-auth" value="false' in profiles["internal"]
    assert 'accept-blind-auth" value="false' in profiles["internal-7060"]
    assert 'accept-blind-auth" value="false' not in profiles["internal-5062"]


def test_compose_gates_xml_curl_and_public_proxy_blocks_internal_routes():
    # Arrange
    compose = yaml.safe_load((ROOT / "docker-compose.app.yml").read_text(encoding="utf-8"))
    proxy = (ROOT / "bunkerweb/server-http/deny-internal.conf").read_text(encoding="utf-8")

    # Act
    healthcheck = " ".join(compose["services"]["freeswitch"]["healthcheck"]["test"])
    config_container = compose["services"]["zenith-freeswitch-config"]["container_name"]

    # Assert
    assert "module_exists mod_xml_curl" in healthcheck
    assert config_container.startswith("zenith-")
    assert "location ^~ /internal/" in proxy
    assert "return 404" in proxy


def test_static_directory_does_not_shadow_exclusive_xml_curl_binding():
    # Arrange
    directory = (ROOT / "freeswitch/conf/directory/default.xml").read_text(encoding="utf-8")

    # Act
    normalized = directory.lower()

    # Assert
    assert "<domain " not in normalized
    assert "extensions.xml" in directory
    assert "LegacyDirectoryProvider" in directory
