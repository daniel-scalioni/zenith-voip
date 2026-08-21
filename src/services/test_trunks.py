from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _service():
    from src.services.trunks import DuplicateIdentityError, ScopeValidationError, TrunkService

    return TrunkService, ScopeValidationError, DuplicateIdentityError


def _repositories(tenant_id="tenant-a"):
    trunk_repository = AsyncMock()
    trunk_repository.find_by.return_value = []
    condominium_repository = AsyncMock()
    pbx_repository = AsyncMock()
    pbx_repository.get.return_value = SimpleNamespace(id="pbx-1", tenant_id=tenant_id)
    condominium_repository.get.return_value = SimpleNamespace(
        id="condo-1", tenant_id=tenant_id, pbx_id="pbx-1", enabled=True
    )
    return trunk_repository, condominium_repository, pbx_repository


@pytest.mark.asyncio
async def test_create_trunk_rejects_cross_tenant_condominium():
    # Arrange
    TrunkService, ScopeValidationError, _ = _service()
    repositories = _repositories(tenant_id="tenant-b")
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    with pytest.raises(ScopeValidationError):
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix="1140", auth_username="ata-1140", password="secret",
            sip_profile="internal", enabled=False,
        )

    # Assert
    repositories[0].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_trunk_rejects_identity_present_in_legacy_directory():
    # Arrange
    TrunkService, _, DuplicateIdentityError = _service()
    repositories = _repositories()
    legacy_provider = AsyncMock()
    legacy_provider.contains.return_value = True
    cipher = AsyncMock()
    service = TrunkService(*repositories, credential_cipher=cipher, legacy_provider=legacy_provider)

    # Act
    with pytest.raises(DuplicateIdentityError):
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix="1140", auth_username="ata-1140", password="secret",
            sip_profile="internal", enabled=False,
        )

    # Assert
    cipher.encrypt.assert_not_called()
    repositories[0].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_trunk_rejects_malformed_prefix():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    with pytest.raises(ValueError, match="invalid_prefix"):
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix="not-digits", auth_username="ata-1140", password="secret",
            sip_profile="internal", enabled=False,
        )

    # Assert
    repositories[0].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_trunk_rejects_sip_profile_outside_allowlist():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    with pytest.raises(ValueError, match="invalid_sip_configuration"):
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix=None, auth_username="ata-1140", password="secret",
            sip_profile="internal-5062", enabled=False,
        )

    # Assert
    repositories[0].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_trunk_rejects_condominium_from_different_pbx_in_same_tenant():
    # Arrange
    TrunkService, ScopeValidationError, _ = _service()
    repositories = _repositories()
    repositories[1].get.return_value = SimpleNamespace(
        id="condo-1", tenant_id="tenant-a", pbx_id="pbx-other", enabled=True,
    )
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    with pytest.raises(ScopeValidationError, match="condominium_not_found"):
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix=None, auth_username="ata-1140", password="secret",
            sip_profile="internal", enabled=False,
        )


@pytest.mark.asyncio
async def test_create_trunk_rejects_whitespace_only_password():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    with pytest.raises(ValueError, match="invalid_password"):
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix="1140", auth_username="ata-1140", password="   ",
            sip_profile="internal", enabled=False,
        )

    # Assert
    repositories[0].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_trunk_translates_concurrent_identity_race_to_duplicate_error():
    # Arrange
    from src.services.base import IntegrityConstraintError

    TrunkService, _, DuplicateIdentityError = _service()
    repositories = _repositories()
    repositories[0].create.side_effect = IntegrityConstraintError(
        'duplicate key value violates unique constraint "uq_ata_trunks_profile_username"'
    )
    legacy_provider = AsyncMock()
    legacy_provider.contains.return_value = False
    cipher = AsyncMock()
    cipher.encrypt.return_value = "encrypted"
    service = TrunkService(*repositories, credential_cipher=cipher, legacy_provider=legacy_provider)

    # Act
    with pytest.raises(DuplicateIdentityError, match="duplicate_auth_identity"):
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix="1140", auth_username="ata-race", password="secret",
            sip_profile="internal", enabled=False,
        )


@pytest.mark.asyncio
async def test_create_trunk_translates_concurrent_prefix_race_to_duplicate_prefix():
    # Arrange
    from src.services.base import IntegrityConstraintError

    TrunkService, _, DuplicateIdentityError = _service()
    repositories = _repositories()
    repositories[0].create.side_effect = IntegrityConstraintError(
        'duplicate key value violates unique constraint "uq_ata_trunks_tenant_prefix"'
    )
    legacy_provider = AsyncMock()
    legacy_provider.contains.return_value = False
    cipher = AsyncMock()
    cipher.encrypt.return_value = "encrypted"
    service = TrunkService(*repositories, credential_cipher=cipher, legacy_provider=legacy_provider)

    # Act
    with pytest.raises(DuplicateIdentityError, match="duplicate_prefix"):
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix="1140", auth_username="ata-race", password="secret",
            sip_profile="internal", enabled=False,
        )


@pytest.mark.asyncio
async def test_create_trunk_translates_foreign_key_race_to_scope_error():
    # Arrange
    from src.services.base import IntegrityConstraintError

    TrunkService, ScopeValidationError, _ = _service()
    repositories = _repositories()
    repositories[0].create.side_effect = IntegrityConstraintError(
        'insert or update on table "ata_trunks" violates foreign key constraint '
        '"ata_trunks_condominium_id_fkey"'
    )
    legacy_provider = AsyncMock()
    legacy_provider.contains.return_value = False
    cipher = AsyncMock()
    cipher.encrypt.return_value = "encrypted"
    service = TrunkService(*repositories, credential_cipher=cipher, legacy_provider=legacy_provider)

    # Act
    with pytest.raises(ScopeValidationError, match="condominium_not_found"):
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix="1140", auth_username="ata-race", password="secret",
            sip_profile="internal", enabled=False,
        )


@pytest.mark.asyncio
async def test_update_trunk_without_password_preserves_existing_cipher():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    existing = SimpleNamespace(
        id="trunk-1", tenant_id="tenant-a", pbx_id="pbx-1",
        condominium_id="condo-1", encrypted_password="existing-token",
        auth_username="ata-1140", sip_profile="internal",
    )
    repositories[0].get.return_value = existing
    legacy_provider = AsyncMock()
    legacy_provider.contains.return_value = False
    cipher = AsyncMock()
    service = TrunkService(*repositories, credential_cipher=cipher, legacy_provider=legacy_provider)

    # Act
    await service.update("tenant-a", "trunk-1", enabled=True)

    # Assert
    cipher.encrypt.assert_not_called()
    repositories[0].update.assert_awaited_once()
    assert "encrypted_password" not in repositories[0].update.await_args.kwargs


@pytest.mark.asyncio
async def test_update_trunk_rejects_whitespace_only_password():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    existing = SimpleNamespace(
        id="trunk-1", tenant_id="tenant-a", pbx_id="pbx-1",
        condominium_id="condo-1", encrypted_password="existing-token",
        auth_username="ata-1140", sip_profile="internal",
    )
    repositories[0].get.return_value = existing
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    with pytest.raises(ValueError, match="invalid_password"):
        await service.update("tenant-a", "trunk-1", password="   ")

    # Assert
    repositories[0].update.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_trunk_translates_check_constraint_to_invalid_prefix():
    # Arrange
    from src.services.base import IntegrityConstraintError

    TrunkService, _, _ = _service()
    repositories = _repositories()
    existing = SimpleNamespace(
        id="trunk-1", tenant_id="tenant-a", pbx_id="pbx-1",
        condominium_id="condo-1", encrypted_password="existing-token",
        auth_username="ata-1140", sip_profile="internal",
    )
    repositories[0].get.return_value = existing
    repositories[0].update.side_effect = IntegrityConstraintError(
        'new row for relation "ata_trunks" violates check constraint "ck_ata_trunks_prefix_digits"'
    )
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    with pytest.raises(ValueError, match="invalid_prefix"):
        await service.update("tenant-a", "trunk-1", prefix="not-digits")


@pytest.mark.asyncio
async def test_trunk_list_scopes_filters_to_tenant():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    repositories[0].find_by.return_value = [SimpleNamespace(id="trunk-1")]
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    result = await service.list("tenant-a", enabled=True, registration_status=None)

    # Assert
    assert result == [SimpleNamespace(id="trunk-1")]
    repositories[0].find_by.assert_awaited_once_with(tenant_id="tenant-a", enabled=True)


@pytest.mark.asyncio
async def test_lookup_directory_identity_returns_none_when_trunk_missing():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    repositories[0].find_by.return_value = []
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    result = await service.lookup_directory_identity("internal-7060", "ata-1140")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_lookup_directory_identity_returns_none_when_trunk_disabled():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    repositories[0].find_by.return_value = [SimpleNamespace(id="trunk-1", enabled=False)]
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    result = await service.lookup_directory_identity("internal-7060", "ata-1140")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_lookup_directory_identity_returns_none_when_condominium_disabled():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    trunk = SimpleNamespace(
        id="trunk-1", enabled=True, tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
    )
    repositories[0].find_by.return_value = [trunk]
    repositories[1].get.return_value = SimpleNamespace(
        id="condo-1", enabled=False, tenant_id="tenant-a", pbx_id="pbx-1",
    )
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    result = await service.lookup_directory_identity("internal-7060", "ata-1140")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_lookup_directory_identity_returns_none_when_data_crosses_tenants():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    trunk = SimpleNamespace(
        id="trunk-1", enabled=True, tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
    )
    repositories[0].find_by.return_value = [trunk]
    repositories[1].get.return_value = SimpleNamespace(
        id="condo-1", enabled=True, tenant_id="tenant-b", pbx_id="pbx-1",
    )
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())

    # Act
    result = await service.lookup_directory_identity("internal-7060", "ata-1140")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_lookup_directory_identity_returns_none_when_tenant_inactive():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    trunk = SimpleNamespace(
        id="trunk-1", enabled=True, tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
    )
    repositories[0].find_by.return_value = [trunk]
    repositories[1].get.return_value = SimpleNamespace(
        id="condo-1", enabled=True, tenant_id="tenant-a", pbx_id="pbx-1",
    )
    tenant_repository = AsyncMock()
    tenant_repository.get.return_value = SimpleNamespace(id="tenant-a", status="suspended")
    service = TrunkService(
        *repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock(),
        tenant_repository=tenant_repository,
    )

    # Act
    result = await service.lookup_directory_identity("internal-7060", "ata-1140")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_lookup_directory_identity_returns_trunk_when_everything_matches():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    trunk = SimpleNamespace(
        id="trunk-1", enabled=True, tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
    )
    repositories[0].find_by.return_value = [trunk]
    repositories[1].get.return_value = SimpleNamespace(
        id="condo-1", enabled=True, tenant_id="tenant-a", pbx_id="pbx-1",
    )
    repositories[2].get.return_value = SimpleNamespace(id="pbx-1", tenant_id="tenant-a")
    tenant_repository = AsyncMock()
    tenant_repository.get.return_value = SimpleNamespace(id="tenant-a", status="active")
    service = TrunkService(
        *repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock(),
        tenant_repository=tenant_repository,
    )

    # Act
    result = await service.lookup_directory_identity("internal-7060", "ata-1140")

    # Assert
    assert result is trunk


@pytest.mark.asyncio
async def test_validate_importable_rejects_existing_identity_owned_by_another_tenant():
    # Arrange
    from src.services.trunk_import import TrunkCSVRow

    TrunkService, ScopeValidationError, _ = _service()
    repositories = _repositories()
    repositories[0].find_by.return_value = [SimpleNamespace(id="foreign-trunk", tenant_id="tenant-b")]
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())
    row = TrunkCSVRow(
        line=1, prefix=None, condominium_name="X", auth_username="1020",
        password="fixture-secret", sip_profile="internal-7060", condominium_id="condo-1",
    )

    # Act
    with pytest.raises(ScopeValidationError, match="trunk_not_found"):
        await service.validate_importable(tenant_id="tenant-a", pbx_id="pbx-1", row=row)


@pytest.mark.asyncio
async def test_update_trunk_encrypts_and_marks_identity_changed_on_valid_password():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    existing = SimpleNamespace(
        id="trunk-1", tenant_id="tenant-a", pbx_id="pbx-1",
        condominium_id="condo-1", encrypted_password="existing-token",
        auth_username="ata-1140", sip_profile="internal",
    )
    repositories[0].get.return_value = existing
    cipher = AsyncMock()
    cipher.encrypt.return_value = "new-encrypted-token"
    service = TrunkService(*repositories, credential_cipher=cipher, legacy_provider=AsyncMock())

    # Act
    await service.update("tenant-a", "trunk-1", password="new-secret")

    # Assert
    cipher.encrypt.assert_called_once_with("new-secret")
    update_kwargs = repositories[0].update.await_args.kwargs
    assert update_kwargs["encrypted_password"] == "new-encrypted-token"
    assert update_kwargs["registration_status"] == "unknown"


@pytest.mark.asyncio
async def test_update_trunk_clears_registration_timestamps_when_identity_becomes_unknown():
    # Arrange
    from datetime import datetime, timezone

    TrunkService, _, _ = _service()
    repositories = _repositories()
    repositories[0].get.return_value = SimpleNamespace(
        id="trunk-1", tenant_id="tenant-a", pbx_id="pbx-1",
        condominium_id="condo-1", encrypted_password="existing-token",
        auth_username="ata-1140", sip_profile="internal",
        last_registered_at=datetime.now(timezone.utc),
        last_unregistered_at=datetime.now(timezone.utc),
    )
    cipher = AsyncMock()
    cipher.encrypt.return_value = "new-encrypted-token"
    service = TrunkService(*repositories, credential_cipher=cipher, legacy_provider=AsyncMock())

    # Act
    await service.update("tenant-a", "trunk-1", password="new-secret")

    # Assert
    update_kwargs = repositories[0].update.await_args.kwargs
    assert update_kwargs["registration_status"] == "unknown"
    assert update_kwargs["last_registered_at"] is None
    assert update_kwargs["last_unregistered_at"] is None


@pytest.mark.asyncio
async def test_update_trunk_rejects_condominium_from_another_tenant():
    # Arrange
    TrunkService, ScopeValidationError, _ = _service()
    repositories = _repositories()
    repositories[0].get.return_value = SimpleNamespace(
        id="trunk-1", tenant_id="tenant-a", pbx_id="pbx-1",
        condominium_id="condo-1", encrypted_password="existing-token",
        auth_username="ata-1140", sip_profile="internal",
    )
    repositories[2].get.return_value = SimpleNamespace(id="pbx-1", tenant_id="tenant-a")
    repositories[1].get.return_value = SimpleNamespace(
        id="condo-foreign", tenant_id="tenant-b", pbx_id="pbx-1"
    )
    service = TrunkService(
        *repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock()
    )

    # Act
    with pytest.raises(ScopeValidationError, match="condominium_not_found"):
        await service.update("tenant-a", "trunk-1", condominium_id="condo-foreign")

    # Assert
    repositories[0].update.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_trunk_rejects_identity_from_legacy_directory():
    # Arrange
    TrunkService, _, DuplicateIdentityError = _service()
    repositories = _repositories()
    repositories[0].get.return_value = SimpleNamespace(
        id="trunk-1", tenant_id="tenant-a", pbx_id="pbx-1",
        condominium_id="condo-1", encrypted_password="existing-token",
        auth_username="ata-1140", sip_profile="internal",
    )
    repositories[0].find_by.return_value = []
    legacy_provider = AsyncMock()
    legacy_provider.contains.return_value = True
    service = TrunkService(
        *repositories, credential_cipher=AsyncMock(), legacy_provider=legacy_provider
    )

    # Act
    with pytest.raises(DuplicateIdentityError, match="duplicate_auth_identity"):
        await service.update("tenant-a", "trunk-1", auth_username="legacy-1001")

    # Assert
    legacy_provider.contains.assert_awaited_once_with("internal", "legacy-1001")
    repositories[0].update.assert_not_awaited()


@pytest.mark.asyncio
async def test_reimport_existing_trunk_clears_stale_registration_timestamps():
    # Arrange
    from datetime import datetime, timezone

    from src.services.trunk_import import TrunkCSVRow

    TrunkService, _, _ = _service()
    repositories = _repositories()
    existing = SimpleNamespace(
        id="trunk-1", tenant_id="tenant-a", pbx_id="pbx-1",
        condominium_id="condo-1", encrypted_password="existing-token",
        auth_username="ata-1140", sip_profile="internal-7060", prefix="1140",
        last_registered_at=datetime.now(timezone.utc),
        last_unregistered_at=datetime.now(timezone.utc),
    )
    repositories[0].find_by.return_value = [existing]
    repositories[0].get.return_value = existing
    cipher = AsyncMock()
    cipher.encrypt.return_value = "new-encrypted-token"
    service = TrunkService(
        *repositories, credential_cipher=cipher, legacy_provider=AsyncMock()
    )
    row = TrunkCSVRow(
        line=1, prefix="1140", condominium_name="Condomínio",
        auth_username="ata-1140", password="new-secret",
        sip_profile="internal-7060", condominium_id="condo-1",
    )

    # Act
    result = await service.upsert_imported(tenant_id="tenant-a", pbx_id="pbx-1", row=row)

    # Assert
    assert result == "updated"
    update_kwargs = repositories[0].update.await_args.kwargs
    assert update_kwargs["registration_status"] == "unknown"
    assert update_kwargs["last_registered_at"] is None
    assert update_kwargs["last_unregistered_at"] is None


@pytest.mark.asyncio
async def test_create_trunk_rejects_global_identity_owned_by_another_tenant_opaquely():
    # Arrange
    TrunkService, _, DuplicateIdentityError = _service()
    repositories = _repositories()
    repositories[0].find_by.return_value = SimpleNamespace(id="foreign-trunk", tenant_id="tenant-b")
    legacy_provider = AsyncMock()
    legacy_provider.contains.return_value = False
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=legacy_provider)

    # Act
    with pytest.raises(DuplicateIdentityError) as error:
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix="1140", auth_username="ata-shared", password="secret",
            sip_profile="internal", enabled=False,
        )

    # Assert
    assert "tenant-b" not in str(error.value)
    assert "foreign-trunk" not in str(error.value)
    repositories[0].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_trunk_rejects_duplicate_prefix_inside_same_tenant():
    # Arrange
    TrunkService, _, DuplicateIdentityError = _service()
    repositories = _repositories()
    repositories[0].find_by.side_effect = [None, SimpleNamespace(id="trunk-previous")]
    legacy_provider = AsyncMock()
    legacy_provider.contains.return_value = False
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=legacy_provider)

    # Act
    with pytest.raises(DuplicateIdentityError):
        await service.create(
            tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
            prefix="1140", auth_username="ata-new", password="secret",
            sip_profile="internal", enabled=False,
        )

    # Assert
    repositories[0].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_trunk_without_prefix_uses_only_sip_identity_uniqueness():
    # Arrange
    TrunkService, _, _ = _service()
    repositories = _repositories()
    legacy_provider = AsyncMock()
    legacy_provider.contains.return_value = False
    cipher = AsyncMock()
    cipher.encrypt.return_value = "encrypted-fixture"
    service = TrunkService(*repositories, credential_cipher=cipher, legacy_provider=legacy_provider)

    # Act
    await service.create(
        tenant_id="tenant-a", pbx_id="pbx-1", condominium_id="condo-1",
        prefix=None, auth_username="1020", password="fixture-secret",
        sip_profile="internal-7060", enabled=False,
    )

    # Assert
    assert repositories[0].find_by.await_count == 1
    repositories[0].find_by.assert_awaited_once_with(
        sip_profile="internal-7060", auth_username="1020"
    )
    assert repositories[0].create.await_args.kwargs["prefix"] is None


@pytest.mark.asyncio
async def test_validate_importable_rejects_cross_tenant_condominium_without_persisting():
    # Arrange
    from src.services.trunk_import import TrunkCSVRow

    TrunkService, ScopeValidationError, _ = _service()
    repositories = _repositories(tenant_id="tenant-b")
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())
    row = TrunkCSVRow(
        line=1, prefix="1140", condominium_name="X", auth_username="ata-1140",
        password="secret", sip_profile="internal", condominium_id="condo-1",
    )

    # Act
    with pytest.raises(ScopeValidationError):
        await service.validate_importable(tenant_id="tenant-a", pbx_id="pbx-1", row=row)

    # Assert
    repositories[0].create.assert_not_awaited()
    repositories[0].update.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_importable_rejects_whitespace_only_password_for_existing_identity():
    # Arrange
    from src.services.trunk_import import TrunkCSVRow

    TrunkService, _, _ = _service()
    repositories = _repositories()
    repositories[0].find_by.return_value = [SimpleNamespace(id="trunk-1", tenant_id="tenant-a")]
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock())
    row = TrunkCSVRow(
        line=1, prefix=None, condominium_name="X", auth_username="1020",
        password="   ", sip_profile="internal-7060", condominium_id="condo-1",
    )

    # Act
    with pytest.raises(ValueError, match="invalid_password"):
        await service.validate_importable(tenant_id="tenant-a", pbx_id="pbx-1", row=row)

    # Assert
    repositories[0].update.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_importable_accepts_new_identity_without_persisting():
    # Arrange
    from src.services.trunk_import import TrunkCSVRow

    TrunkService, _, _ = _service()
    repositories = _repositories()
    legacy_provider = AsyncMock()
    legacy_provider.contains.return_value = False
    service = TrunkService(*repositories, credential_cipher=AsyncMock(), legacy_provider=legacy_provider)
    row = TrunkCSVRow(
        line=1, prefix=None, condominium_name="X", auth_username="1020",
        password="fixture-secret", sip_profile="internal-7060", condominium_id="condo-1",
    )

    # Act
    await service.validate_importable(tenant_id="tenant-a", pbx_id="pbx-1", row=row)

    # Assert
    repositories[0].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_without_prefix_resolves_existing_by_sip_identity():
    # Arrange
    from src.services.trunk_import import TrunkCSVRow

    TrunkService, _, _ = _service()
    repositories = _repositories()
    existing = SimpleNamespace(id="trunk-1", tenant_id="tenant-a")
    repositories[0].find_by.return_value = [existing]
    service = TrunkService(
        *repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock()
    )
    service.update = AsyncMock()
    row = TrunkCSVRow(
        line=1, prefix=None, condominium_name="Parque Portugal",
        auth_username="1020", password="fixture-secret",
        sip_profile="internal-7060", condominium_id="condo-1",
    )

    # Act
    result = await service.upsert_imported(tenant_id="tenant-a", pbx_id="pbx-1", row=row)

    # Assert
    assert result == "updated"
    repositories[0].find_by.assert_awaited_once_with(
        sip_profile="internal-7060", auth_username="1020"
    )


@pytest.mark.asyncio
async def test_upsert_with_new_prefix_still_resolves_existing_by_sip_identity():
    # Arrange
    from src.services.trunk_import import TrunkCSVRow

    TrunkService, _, _ = _service()
    repositories = _repositories()
    existing = SimpleNamespace(id="trunk-1", tenant_id="tenant-a", prefix=None)
    repositories[0].find_by.return_value = [existing]
    service = TrunkService(
        *repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock()
    )
    service.update = AsyncMock()
    row = TrunkCSVRow(
        line=1, prefix="1020", condominium_name="Parque Portugal",
        auth_username="1020", password="fixture-secret",
        sip_profile="internal-7060", condominium_id="condo-1",
    )

    # Act
    result = await service.upsert_imported(tenant_id="tenant-a", pbx_id="pbx-1", row=row)

    # Assert
    assert result == "updated"
    repositories[0].find_by.assert_awaited_once_with(
        sip_profile="internal-7060", auth_username="1020"
    )
    service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_global_identity_never_updates_a_foreign_tenant_trunk():
    # Arrange
    from src.services.trunk_import import TrunkCSVRow

    TrunkService, ScopeValidationError, _ = _service()
    repositories = _repositories()
    foreign = SimpleNamespace(id="foreign-trunk", tenant_id="tenant-b")
    repositories[0].find_by.return_value = [foreign]
    repositories[0].get.return_value = foreign
    service = TrunkService(
        *repositories, credential_cipher=AsyncMock(), legacy_provider=AsyncMock()
    )
    row = TrunkCSVRow(
        line=1, prefix=None, condominium_name="Parque Portugal",
        auth_username="1020", password="fixture-secret",
        sip_profile="internal-7060", condominium_id="condo-1",
    )

    # Act
    with pytest.raises(ScopeValidationError, match="trunk_not_found"):
        await service.upsert_imported(tenant_id="tenant-a", pbx_id="pbx-1", row=row)

    # Assert
    repositories[0].update.assert_not_awaited()
