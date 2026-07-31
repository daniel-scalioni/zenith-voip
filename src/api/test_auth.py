from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from src.api.auth import create_access_token, require_admin_role, verify_token
from src.config import settings


def _make_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_create_access_token_generates_verifiable_payload():
    # Arrange
    subject, tenant_id, role = "user1", "t1", "agent"

    # Act
    token = create_access_token(subject=subject, tenant_id=tenant_id, role=role)
    payload = verify_token(_make_credentials(token))

    # Assert
    assert isinstance(token, str)
    assert payload["sub"] == subject
    assert payload["tenant_id"] == tenant_id
    assert payload["role"] == role
    assert "exp" in payload
    assert "iat" in payload


def test_create_access_token_respects_custom_expires_delta():
    # Arrange
    custom_delta = timedelta(minutes=30)

    # Act
    token = create_access_token(subject="u", expires_delta=custom_delta)
    payload = verify_token(_make_credentials(token))

    # Assert
    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    diff = exp_time - datetime.now(timezone.utc)
    assert 29 <= diff.total_seconds() / 60 <= 31


def test_verify_token_returns_payload_for_valid_token():
    # Arrange
    token = create_access_token(subject="user1", tenant_id="t1", role="agent")
    creds = _make_credentials(token)

    # Act
    payload = verify_token(creds)

    # Assert
    assert payload["sub"] == "user1"
    assert payload["tenant_id"] == "t1"
    assert payload["role"] == "agent"


def test_verify_token_rejects_malformed_token():
    # Arrange
    creds = _make_credentials("not-a-jwt-token")

    # Act
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)

    # Assert
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_verify_token_rejects_invalid_signature():
    # Arrange
    token = jwt.encode(
        {"sub": "user", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        "wrong-secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    creds = _make_credentials(token)

    # Act
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)

    # Assert
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_verify_token_rejects_expired_token():
    # Arrange
    token = create_access_token(subject="user", expires_delta=timedelta(seconds=-1))
    creds = _make_credentials(token)

    # Act
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)

    # Assert
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_verify_token_rejects_unsupported_algorithm():
    # Arrange
    mismatched_algorithm = "HS512" if settings.JWT_ALGORITHM != "HS512" else "HS384"
    token = jwt.encode(
        {"sub": "user", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        settings.JWT_SECRET,
        algorithm=mismatched_algorithm,
    )
    creds = _make_credentials(token)

    # Act
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)

    # Assert
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_require_admin_role_allows_tenant_admin():
    # Arrange
    token = create_access_token(subject="admin", role="tenant_admin")
    payload = verify_token(_make_credentials(token))

    # Act
    result = require_admin_role(payload)

    # Assert
    assert result["role"] == "tenant_admin"


def test_require_admin_role_rejects_agent_role():
    # Arrange
    token = create_access_token(subject="agent", role="agent")
    payload = verify_token(_make_credentials(token))

    # Act
    with pytest.raises(HTTPException) as exc_info:
        require_admin_role(payload)

    # Assert
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Apenas administradores de inquilino podem realizar esta ação."
    assert exc_info.value.headers is None


def test_require_admin_role_rejects_missing_role():
    # Arrange
    payload = {"sub": "user", "tenant_id": "t1"}

    # Act
    with pytest.raises(HTTPException) as exc_info:
        require_admin_role(payload)

    # Assert
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Apenas administradores de inquilino podem realizar esta ação."
    assert exc_info.value.headers is None


def test_require_admin_role_rejects_none_role():
    # Arrange
    payload = {"sub": "user", "tenant_id": "t1", "role": None}

    # Act
    with pytest.raises(HTTPException) as exc_info:
        require_admin_role(payload)

    # Assert
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Apenas administradores de inquilino podem realizar esta ação."
    assert exc_info.value.headers is None


def test_require_admin_role_rejects_empty_role():
    # Arrange
    payload = {"sub": "user", "role": ""}

    # Act
    with pytest.raises(HTTPException) as exc_info:
        require_admin_role(payload)

    # Assert
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Apenas administradores de inquilino podem realizar esta ação."
    assert exc_info.value.headers is None
