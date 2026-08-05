import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).with_name("legacy_sip_register.py")
    spec = importlib.util.spec_from_file_location("legacy_sip_register", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_digest_authorization_supports_qop_auth_without_leaking_password():
    # Arrange
    module = _module()
    challenge = 'Digest realm="zenith.local", nonce="abc123", algorithm=MD5, qop="auth"'
    password = "canary-secret"

    # Act
    authorization = module.build_digest_authorization(
        challenge=challenge,
        username="legacy-user",
        password=password,
        method="REGISTER",
        uri="sip:10.10.10.11",
        nonce_count=1,
        cnonce="fixed-cnonce",
    )

    # Assert
    assert authorization.startswith("Digest ")
    assert 'qop=auth' in authorization
    assert 'nc=00000001' in authorization
    assert password not in authorization


def test_sanitized_result_contains_only_status_and_identity_digest():
    # Arrange
    module = _module()

    # Act
    result = module.sanitized_result("legacy-user", 200, 200)

    # Assert
    assert set(result) == {"register_status", "unregister_status", "identity_sha256"}
    assert "legacy-user" not in repr(result)


def test_build_digest_authorization_supports_challenge_without_qop():
    # Arrange
    module = _module()
    challenge = 'Digest realm="zenith.local", nonce="abc123", algorithm=MD5'

    # Act
    authorization = module.build_digest_authorization(
        challenge=challenge,
        username="legacy-user",
        password="fixture-secret",
        method="REGISTER",
        uri="sip:10.10.10.11",
        nonce_count=1,
        cnonce="fixed-cnonce",
    )

    # Assert
    assert "qop=" not in authorization
    assert "nc=" not in authorization
    assert "response=" in authorization


def test_build_digest_authorization_rejects_auth_int_only_challenge():
    # Arrange
    import pytest

    module = _module()
    challenge = 'Digest realm="zenith.local", nonce="abc123", qop="auth-int"'

    # Act
    with pytest.raises(RuntimeError, match="sip_qop_unsupported"):
        module.build_digest_authorization(
            challenge=challenge,
            username="legacy-user",
            password="fixture-secret",
            method="REGISTER",
            uri="sip:10.10.10.11",
            nonce_count=1,
            cnonce="fixed-cnonce",
        )

    # Assert
    assert "fixture-secret" not in repr(module)
