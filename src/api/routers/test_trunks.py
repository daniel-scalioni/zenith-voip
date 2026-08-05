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
