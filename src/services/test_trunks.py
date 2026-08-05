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
