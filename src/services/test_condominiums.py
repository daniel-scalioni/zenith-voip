from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _service():
    from src.services.trunks import CondominiumService, ScopeValidationError

    return CondominiumService, ScopeValidationError


@pytest.mark.asyncio
async def test_create_condominium_rejects_pbx_from_another_tenant():
    # Arrange
    CondominiumService, ScopeValidationError = _service()
    pbx_repository = AsyncMock()
    pbx_repository.get.return_value = SimpleNamespace(id="pbx-1", tenant_id="tenant-b")
    condominium_repository = AsyncMock()
    service = CondominiumService(condominium_repository, pbx_repository)

    # Act
    with pytest.raises(ScopeValidationError):
        await service.create("tenant-a", "pbx-1", "Condominio A")

    # Assert
    condominium_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_condominium_is_idempotent_by_tenant_pbx_and_name():
    # Arrange
    CondominiumService, _ = _service()
    existing = SimpleNamespace(id="condo-1", name="Condominio A")
    pbx_repository = AsyncMock()
    pbx_repository.get.return_value = SimpleNamespace(id="pbx-1", tenant_id="tenant-a")
    condominium_repository = AsyncMock()
    condominium_repository.find_by.return_value = [existing]
    service = CondominiumService(condominium_repository, pbx_repository)

    # Act
    result = await service.create("tenant-a", "pbx-1", "Condominio A")

    # Assert
    assert result is existing
    condominium_repository.create.assert_not_awaited()
