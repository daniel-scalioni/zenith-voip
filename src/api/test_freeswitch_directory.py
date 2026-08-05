import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.config import settings
from src.main import app


def _directory():
    from src.api.freeswitch_directory import build_directory_xml, extract_directory_lookup

    return build_directory_xml, extract_directory_lookup


def test_build_directory_xml_escapes_values_and_includes_authenticated_context():
    # Arrange
    build_directory_xml, _ = _directory()
    canary_password = 'fixture-<&"-secret'
    user = {
        "auth_username": "ata<&1140",
        "password": canary_password,
        "tenant_id": "tenant-1",
        "pbx_id": "pbx-1",
        "condominium_id": "condo-1",
        "trunk_id": "trunk-1",
        "prefix": "1140",
    }

    # Act
    payload = build_directory_xml("zenith.local", user)
    root = ET.fromstring(payload)

    # Assert
    assert root.tag == "document"
    assert "&lt;" in payload
    assert root.find(".//param[@name='password']").attrib["value"] == canary_password
    assert root.find(".//variable[@name='zenith_trunk_id']").attrib["value"] == "trunk-1"


def test_build_directory_xml_omits_optional_prefix_when_absent():
    # Arrange
    build_directory_xml, _ = _directory()
    user = {
        "auth_username": "1020",
        "password": "fixture-secret",
        "tenant_id": "tenant-1",
        "pbx_id": "pbx-1",
        "condominium_id": "condo-1",
        "trunk_id": "trunk-1",
        "prefix": None,
    }

    # Act
    payload = build_directory_xml("zenith.local", user)
    root = ET.fromstring(payload)

    # Assert
    assert root.find(".//variable[@name='zenith_trunk_prefix']") is None


def test_extract_lookup_rejects_non_directory_section():
    # Arrange
    _, extract_directory_lookup = _directory()

    # Act
    result = extract_directory_lookup({"section": "dialplan", "user": "ata-1"})

    # Assert
    assert result is None


def test_extract_lookup_requires_profile_and_username_without_logging_body(caplog):
    # Arrange
    _, extract_directory_lookup = _directory()
    canary = "canary-form-secret"

    # Act
    result = extract_directory_lookup({"section": "directory", "password": canary})

    # Assert
    assert result is None
    assert canary not in caplog.text


def test_extract_lookup_accepts_real_freeswitch_sip_profile_field():
    # Arrange
    _, extract_directory_lookup = _directory()
    form = {
        "section": "directory",
        "sip_profile": "internal",
        "sip_auth_username": "spike012",
        "key_value": "zenith.local",
    }

    # Act
    result = extract_directory_lookup(form)

    # Assert
    assert result == ("internal", "spike012")


def test_extract_lookup_prefers_canonical_fields_and_never_uses_domain_as_username():
    # Arrange
    _, extract_directory_lookup = _directory()
    conflicting = {
        "section": "directory",
        "sip_profile": "internal",
        "sip_profile_name": "wrong-profile",
        "sip_auth_username": "spike012",
        "user": "wrong-user",
        "key_value": "zenith.local",
    }
    domain_only = {
        "section": "directory",
        "sip_profile": "internal",
        "key_value": "zenith.local",
    }

    # Act
    preferred = extract_directory_lookup(conflicting)
    rejected = extract_directory_lookup(domain_only)

    # Assert
    assert preferred == ("internal", "spike012")
    assert rejected is None


def _override_directory_service(service):
    from src.api.freeswitch_directory import get_directory_lookup_service

    app.dependency_overrides[get_directory_lookup_service] = lambda: service
    return get_directory_lookup_service


def test_directory_endpoint_uses_real_freeswitch_envelope_end_to_end(monkeypatch):
    # Arrange
    service = AsyncMock()
    service.lookup.return_value = {
        "auth_username": "spike012",
        "password": "fixture-sip-password",
        "tenant_id": "tenant-1",
        "pbx_id": "pbx-1",
        "condominium_id": "condo-1",
        "trunk_id": "trunk-1",
        "prefix": "1140",
    }
    dependency = _override_directory_service(service)
    monkeypatch.setattr(settings, "FREESWITCH_DIRECTORY_BASIC_USERNAME", "fixture-user", raising=False)
    monkeypatch.setattr(settings, "FREESWITCH_DIRECTORY_BASIC_PASSWORD", "fixture-password", raising=False)

    try:
        # Act
        response = TestClient(app).post(
            "/internal/freeswitch/directory",
            data={
                "section": "directory",
                "sip_profile": "internal",
                "sip_auth_username": "spike012",
                "key_value": "zenith.local",
            },
            auth=("fixture-user", "fixture-password"),
        )
    finally:
        app.dependency_overrides.pop(dependency, None)

    # Assert
    assert response.status_code == 200
    service.lookup.assert_awaited_once_with("internal", "spike012")
    root = ET.fromstring(response.text)
    assert root.find(".//domain").attrib["name"] == "zenith.local"
    assert root.find(".//user").attrib["id"] == "spike012"


def test_directory_endpoint_rejects_missing_basic_auth_without_exposing_xml(caplog):
    # Arrange
    service = AsyncMock()
    dependency = _override_directory_service(service)
    canary = "canary-form-secret"

    try:
        # Act
        response = TestClient(app).post(
            "/internal/freeswitch/directory",
            data={"section": "directory", "sip_profile_name": "internal", "user": "ata-1", "ignored": canary},
        )
    finally:
        app.dependency_overrides.pop(dependency, None)

    # Assert
    assert response.status_code == 401
    assert "<user" not in response.text
    assert canary not in response.text
    assert canary not in caplog.text
    service.lookup.assert_not_awaited()


def test_directory_endpoint_returns_no_store_not_found_for_valid_basic(monkeypatch):
    # Arrange
    service = AsyncMock()
    service.lookup.return_value = None
    dependency = _override_directory_service(service)
    monkeypatch.setattr(settings, "FREESWITCH_DIRECTORY_BASIC_USERNAME", "fixture-user", raising=False)
    monkeypatch.setattr(settings, "FREESWITCH_DIRECTORY_BASIC_PASSWORD", "fixture-password", raising=False)

    try:
        # Act
        response = TestClient(app).post(
            "/internal/freeswitch/directory",
            data={"section": "directory", "sip_profile_name": "internal", "user": "missing"},
            auth=("fixture-user", "fixture-password"),
        )
    finally:
        app.dependency_overrides.pop(dependency, None)

    # Assert
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("application/xml")
    assert "not found" in response.text.lower()


def test_directory_endpoint_fails_closed_when_database_and_legacy_collide(monkeypatch):
    # Arrange
    from src.api.freeswitch_directory import AmbiguousDirectoryIdentityError

    service = AsyncMock()
    service.lookup.side_effect = AmbiguousDirectoryIdentityError()
    dependency = _override_directory_service(service)
    monkeypatch.setattr(settings, "FREESWITCH_DIRECTORY_BASIC_USERNAME", "fixture-user", raising=False)
    monkeypatch.setattr(settings, "FREESWITCH_DIRECTORY_BASIC_PASSWORD", "fixture-password", raising=False)

    try:
        # Act
        response = TestClient(app).post(
            "/internal/freeswitch/directory",
            data={"section": "directory", "sip_profile_name": "internal", "user": "shared"},
            auth=("fixture-user", "fixture-password"),
        )
    finally:
        app.dependency_overrides.pop(dependency, None)

    # Assert
    assert response.status_code == 200
    assert "<user" not in response.text
    assert "not found" in response.text.lower()


def test_directory_endpoint_returns_sanitized_503_when_key_is_unavailable(monkeypatch, caplog):
    # Arrange
    from src.api.freeswitch_directory import DirectoryCredentialUnavailableError

    service = AsyncMock()
    service.lookup.side_effect = DirectoryCredentialUnavailableError("trunk-1")
    dependency = _override_directory_service(service)
    monkeypatch.setattr(settings, "FREESWITCH_DIRECTORY_BASIC_USERNAME", "fixture-user", raising=False)
    monkeypatch.setattr(settings, "FREESWITCH_DIRECTORY_BASIC_PASSWORD", "fixture-password", raising=False)
    canary = "fixture-canary-secret"

    try:
        # Act
        response = TestClient(app).post(
            "/internal/freeswitch/directory",
            data={"section": "directory", "sip_profile_name": "internal", "user": "ata-1", "ignored": canary},
            auth=("fixture-user", "fixture-password"),
        )
    finally:
        app.dependency_overrides.pop(dependency, None)

    # Assert
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "credential_key_unavailable"}}
    assert canary not in response.text
    assert canary not in caplog.text


def test_xml_response_fails_closed_above_64_kib():
    # Arrange
    from src.api.freeswitch_directory import _xml_response

    oversized = "<document>" + ("x" * 70_000) + "</document>"

    # Act
    response = _xml_response(oversized)

    # Assert
    assert len(response.body) <= 65_536
    assert b"not found" in response.body.lower()
