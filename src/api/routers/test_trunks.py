import pytest
from fastapi.testclient import TestClient

from src.api.auth import create_access_token, require_admin_role
from src.main import app


def test_trunk_admin_routes_are_registered_under_admin_prefix():
    # Arrange
    expected = {
        ("/api/v1/admin/condominiums", "POST"),
        ("/api/v1/admin/condominiums", "GET"),
        ("/api/v1/admin/trunks", "POST"),
        ("/api/v1/admin/trunks", "GET"),
        ("/api/v1/admin/trunks/import", "POST"),
    }

    # Act
    actual = {(route.path, method) for route in app.routes for method in getattr(route, "methods", set())}

    # Assert
    assert expected <= actual


def test_trunk_response_schema_excludes_plain_and_encrypted_password():
    # Arrange
    from src.api.routers.trunks import TrunkResponse

    # Act
    fields = set(TrunkResponse.model_fields)

    # Assert
    assert "password" not in fields
    assert "encrypted_password" not in fields
    assert {"active_calls", "in_use", "registration_status"} <= fields


def test_trunk_create_accepts_missing_prefix_without_inference():
    # Arrange
    from src.api.routers.trunks import TrunkCreate

    # Act
    payload = TrunkCreate(
        pbx_id="pbx-1", condominium_id="condo-1", auth_username="1020",
        password="fixture-secret", sip_profile="internal-7060",
    )

    # Assert
    assert payload.prefix is None


def test_trunk_admin_rejects_non_admin_role():
    # Arrange
    token = create_access_token("agent-1", tenant_id="tenant-a", role="agent")

    # Act
    response = TestClient(app).get(
        "/api/v1/admin/trunks", headers={"Authorization": f"Bearer {token}"}
    )

    # Assert
    assert response.status_code == 403


def test_map_service_error_reraises_unmapped_exception():
    # Arrange
    from src.api.routers.trunks import _map_service_error

    error = RuntimeError("fixture-unmapped")

    # Act / Assert
    with pytest.raises(RuntimeError, match="fixture-unmapped"):
        _map_service_error(error)


def test_trunk_create_maps_scope_validation_error_to_404():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_trunk_service
    from src.services.trunks import ScopeValidationError

    service = AsyncMock()
    service.create.side_effect = ScopeValidationError("condominium_not_found")
    token = create_access_token("admin-1", tenant_id="tenant-a", role="tenant_admin")
    app.dependency_overrides[get_trunk_service] = lambda: service

    try:
        # Act
        response = TestClient(app).post(
            "/api/v1/admin/trunks",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "pbx_id": "pbx-1", "condominium_id": "condo-1",
                "auth_username": "ata-1", "password": "secret",
                "sip_profile": "internal",
            },
        )
    finally:
        app.dependency_overrides.pop(get_trunk_service, None)

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "condominium_not_found"


def test_trunk_create_maps_duplicate_identity_error_to_409():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_trunk_service
    from src.services.trunks import DuplicateIdentityError

    service = AsyncMock()
    service.create.side_effect = DuplicateIdentityError("duplicate_auth_identity")
    token = create_access_token("admin-1", tenant_id="tenant-a", role="tenant_admin")
    app.dependency_overrides[get_trunk_service] = lambda: service

    try:
        # Act
        response = TestClient(app).post(
            "/api/v1/admin/trunks",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "pbx_id": "pbx-1", "condominium_id": "condo-1",
                "auth_username": "ata-1", "password": "secret",
                "sip_profile": "internal",
            },
        )
    finally:
        app.dependency_overrides.pop(get_trunk_service, None)

    # Assert
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "duplicate_auth_identity"


def _fake_trunk(**overrides):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    defaults = {
        "id": "trunk-1", "tenant_id": "tenant-a", "pbx_id": "pbx-1",
        "condominium_id": "condo-1", "prefix": "1140", "auth_username": "ata-11405678",
        "sip_profile": "internal-7060", "transport": "udp", "enabled": True,
        "registration_status": "registered", "last_registered_at": datetime.now(timezone.utc),
        "last_unregistered_at": None, "last_error_code": None, "last_error_at": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_trunk_create_returns_serialized_response_with_masked_username():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_trunk_service

    service = AsyncMock()
    service.create.return_value = _fake_trunk()
    token = create_access_token("admin-1", tenant_id="tenant-a", role="tenant_admin")
    app.dependency_overrides[get_trunk_service] = lambda: service

    try:
        # Act
        response = TestClient(app).post(
            "/api/v1/admin/trunks",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "pbx_id": "pbx-1", "condominium_id": "condo-1", "prefix": "1140",
                "auth_username": "ata-11405678", "password": "secret",
                "sip_profile": "internal-7060",
            },
        )
    finally:
        app.dependency_overrides.pop(get_trunk_service, None)

    # Assert
    body = response.json()
    assert response.status_code == 201
    assert body["auth_username_masked"] == "***5678"
    assert "password" not in body
    assert "encrypted_password" not in body


def test_trunk_view_masks_short_usernames_fully():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_trunk_service

    service = AsyncMock()
    service.create.return_value = _fake_trunk(auth_username="ab")
    token = create_access_token("admin-1", tenant_id="tenant-a", role="tenant_admin")
    app.dependency_overrides[get_trunk_service] = lambda: service

    try:
        # Act
        response = TestClient(app).post(
            "/api/v1/admin/trunks",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "pbx_id": "pbx-1", "condominium_id": "condo-1",
                "auth_username": "ab", "password": "secret",
                "sip_profile": "internal-7060",
            },
        )
    finally:
        app.dependency_overrides.pop(get_trunk_service, None)

    # Assert
    assert response.json()["auth_username_masked"] == "***"


def test_list_trunks_returns_serialized_items():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_trunk_service

    service = AsyncMock()
    service.list.return_value = [_fake_trunk()]
    token = create_access_token("admin-1", tenant_id="tenant-a", role="tenant_admin")
    app.dependency_overrides[get_trunk_service] = lambda: service

    try:
        # Act
        response = TestClient(app).get(
            "/api/v1/admin/trunks", headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.pop(get_trunk_service, None)

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["registration_status"] == "registered"
    # active_calls/in_use ainda não são preenchidos por list_trunks/create_trunk
    # (TrunkStateService.active_calls nunca é chamado no router) — gap conhecido W007,
    # este teste documenta o comportamento atual, não a especificação correta.
    assert body[0]["active_calls"] == 0
    assert body[0]["in_use"] is False


def _fake_condominium(**overrides):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    defaults = {
        "id": "condo-1", "tenant_id": "tenant-a", "pbx_id": "pbx-1",
        "name": "Parque Portugal", "external_id": "vital-123", "enabled": True,
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_condominium_create_returns_serialized_response():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_condominium_service

    service = AsyncMock()
    service.create.return_value = _fake_condominium()
    token = create_access_token("admin-1", tenant_id="tenant-a", role="tenant_admin")
    app.dependency_overrides[get_condominium_service] = lambda: service

    try:
        # Act
        response = TestClient(app).post(
            "/api/v1/admin/condominiums",
            headers={"Authorization": f"Bearer {token}"},
            json={"pbx_id": "pbx-1", "name": "Parque Portugal"},
        )
    finally:
        app.dependency_overrides.pop(get_condominium_service, None)

    # Assert
    assert response.status_code == 201
    assert response.json()["name"] == "Parque Portugal"


def test_list_condominiums_returns_serialized_items():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_condominium_service

    service = AsyncMock()
    service.list.return_value = [_fake_condominium()]
    token = create_access_token("admin-1", tenant_id="tenant-a", role="tenant_admin")
    app.dependency_overrides[get_condominium_service] = lambda: service

    try:
        # Act
        response = TestClient(app).get(
            "/api/v1/admin/condominiums", headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.pop(get_condominium_service, None)

    # Assert
    assert response.status_code == 200
    assert response.json()[0]["external_id"] == "vital-123"


def test_import_trunks_returns_dry_run_result():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_trunk_service

    service = AsyncMock()
    token = create_access_token("admin-1", tenant_id="tenant-a", role="tenant_admin")
    app.dependency_overrides[get_trunk_service] = lambda: service
    csv_content = b"technology,device_user,device_password\nsip,ata-1,fixture-secret\n"

    try:
        # Act
        response = TestClient(app).post(
            "/api/v1/admin/trunks/import?pbx_id=pbx-1&dry_run=true",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("trunks.csv", csv_content, "text/csv")},
        )
    finally:
        app.dependency_overrides.pop(get_trunk_service, None)

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["rows"] == 1
    service.upsert_imported.assert_not_awaited()


def test_import_trunks_maps_csv_schema_error_to_422():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_trunk_service

    service = AsyncMock()
    token = create_access_token("admin-1", tenant_id="tenant-a", role="tenant_admin")
    app.dependency_overrides[get_trunk_service] = lambda: service
    bad_content = b"only,two,columns\na,b,c\n"

    try:
        # Act
        response = TestClient(app).post(
            "/api/v1/admin/trunks/import?pbx_id=pbx-1&dry_run=true",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("trunks.csv", bad_content, "text/csv")},
        )
    finally:
        app.dependency_overrides.pop(get_trunk_service, None)

    # Assert
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "csv_schema_invalid"


def test_trunk_create_maps_plain_value_error_to_400():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_trunk_service

    service = AsyncMock()
    service.create.side_effect = ValueError("invalid_sip_configuration")
    token = create_access_token("admin-1", tenant_id="tenant-a", role="tenant_admin")
    app.dependency_overrides[get_trunk_service] = lambda: service

    try:
        # Act
        response = TestClient(app).post(
            "/api/v1/admin/trunks",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "pbx_id": "pbx-1", "condominium_id": "condo-1",
                "auth_username": "ata-1", "password": "secret",
                "sip_profile": "internal",
            },
        )
    finally:
        app.dependency_overrides.pop(get_trunk_service, None)

    # Assert
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_sip_configuration"


def test_trunk_admin_tenant_scope_comes_only_from_token():
    # Arrange
    from unittest.mock import AsyncMock

    from src.api.routers.trunks import get_trunk_service

    service = AsyncMock()
    service.list.return_value = []
    app.dependency_overrides[require_admin_role] = lambda: {
        "sub": "admin-1", "tenant_id": "tenant-a", "role": "tenant_admin"
    }
    app.dependency_overrides[get_trunk_service] = lambda: service

    try:
        # Act
        response = TestClient(app).get("/api/v1/admin/trunks?tenant_id=tenant-b")
    finally:
        app.dependency_overrides.pop(require_admin_role, None)
        app.dependency_overrides.pop(get_trunk_service, None)

    # Assert
    assert response.status_code == 200
    assert service.list.await_args.args[0] == "tenant-a"
    assert "tenant-b" not in service.list.await_args.args
