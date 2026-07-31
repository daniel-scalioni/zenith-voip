from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from src.api.auth import create_access_token, require_admin_role, verify_token
from src.config import settings


def _make_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_create_access_token_returns_string():
    # Arrange
    token = create_access_token(subject="user1", tenant_id="t1", role="agent")

    # Act
    decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

    # Assert
    assert isinstance(token, str)
    assert decoded["sub"] == "user1"
    assert decoded["tenant_id"] == "t1"
    assert decoded["role"] == "agent"
    assert "exp" in decoded
    assert "iat" in decoded


def test_create_access_token_with_custom_expiry():
    # Arrange
    token = create_access_token(subject="u", expires_delta=timedelta(minutes=30))
    decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

    # Act
    now = datetime.now(timezone.utc)
    exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    diff = exp_time - now

    # Assert
    assert 25 <= diff.total_seconds() / 60 <= 35


def test_verify_token_returns_payload():
    # Arrange
    token = create_access_token(subject="user1", tenant_id="t1", role="agent")
    creds = _make_credentials(token)

    # Act
    payload = verify_token(creds)

    # Assert
    assert payload["sub"] == "user1"
    assert payload["tenant_id"] == "t1"


def test_verify_token_rejects_invalid_token():
    # Arrange
    creds = _make_credentials("invalid.jwt.token")

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)
    assert exc_info.value.status_code == 401


def test_verify_token_rejects_expired_token():
    # Arrange
    payload = {
        "sub": "user",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    creds = _make_credentials(token)

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)
    assert exc_info.value.status_code == 401


def test_verify_token_rejects_wrong_secret():
    # Arrange
    token = jwt.encode(
        {"sub": "user", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        "wrong-secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    creds = _make_credentials(token)

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)
    assert exc_info.value.status_code == 401


def test_require_admin_role_allows_tenant_admin():
    # Arrange
    token = create_access_token(subject="admin", role="tenant_admin")
    creds = _make_credentials(token)
    payload = verify_token(creds)

    # Act
    result = require_admin_role(payload)

    # Assert
    assert result["role"] == "tenant_admin"


def test_require_admin_role_rejects_agent():
    # Arrange
    token = create_access_token(subject="agent", role="agent")
    creds = _make_credentials(token)
    payload = verify_token(creds)

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        require_admin_role(payload)
    assert exc_info.value.status_code == 403


def test_require_admin_role_rejects_missing_role():
    # Arrange
    payload = {"sub": "user", "tenant_id": "t1"}

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        require_admin_role(payload)
    assert exc_info.value.status_code == 403


def test_require_admin_role_rejects_empty_role():
    # Arrange
    payload = {"sub": "user", "role": ""}

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        require_admin_role(payload)
    assert exc_info.value.status_code == 403
