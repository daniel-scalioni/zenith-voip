"""API administrativa tenant-scoped para condomínios e troncos ATA."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, model_validator
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_admin_role
from src.config import settings
from src.database.database import get_db
from src.database.models import ATATrunk, Condominium, PBX
from src.events.redis_streams import event_bus
from src.services.base import Repository
from src.services.legacy_directory import LegacyDirectoryProvider
from src.services.trunk_credentials import CredentialConfigurationError, TrunkCredentialCipher
from src.services.trunk_import import CSVSchemaError, import_trunk_csv
from src.services.trunks import (
    CondominiumService, DuplicateIdentityError, ScopeValidationError, TrunkService,
)
from src.telephony.trunk_state import (
    TrunkIdentityResolver, TrunkStateRepository, TrunkStateService,
)

router = APIRouter(prefix="/api/v1/admin", tags=["trunks"])
logger = logging.getLogger(__name__)


class CondominiumCreate(BaseModel):
    pbx_id: str
    name: str = Field(min_length=1, max_length=128)
    external_id: str | None = Field(default=None, max_length=128)
    enabled: bool = True


class CondominiumResponse(BaseModel):
    id: str
    tenant_id: str
    pbx_id: str
    name: str
    external_id: str | None = None
    enabled: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CondominiumUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    external_id: str | None = Field(default=None, max_length=128)
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("empty_patch")
        for field_name in {"name", "enabled"}:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name}_cannot_be_null")
        return self


class TrunkCreate(BaseModel):
    pbx_id: str
    condominium_id: str
    prefix: str | None = Field(default=None, pattern=r"^[0-9]{1,32}$")
    auth_username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1)
    sip_profile: str
    transport: str = "udp"
    enabled: bool = False


class TrunkResponse(BaseModel):
    id: str
    tenant_id: str
    pbx_id: str
    condominium_id: str
    prefix: str | None = None
    auth_username_masked: str
    sip_profile: str
    transport: str
    enabled: bool
    registration_status: str
    active_calls: int = 0
    in_use: bool = False
    last_registered_at: datetime | None = None
    last_unregistered_at: datetime | None = None
    last_error_code: str | None = None
    last_error_at: datetime | None = None


class TrunkUpdate(BaseModel):
    condominium_id: str | None = Field(default=None, min_length=1)
    prefix: str | None = Field(default=None, pattern=r"^[0-9]{1,32}$")
    auth_username: str | None = Field(default=None, min_length=1, max_length=128)
    password: str | None = Field(default=None, min_length=1)
    sip_profile: Literal["internal", "internal-7060"] | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("empty_patch")
        for field_name in {
            "condominium_id", "auth_username", "password", "sip_profile", "enabled"
        }:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name}_cannot_be_null")
        return self


def _keys() -> list[str]:
    return [item.strip() for item in settings.TRUNK_CREDENTIAL_KEYS.split(",") if item.strip()]


def get_condominium_service(db: AsyncSession = Depends(get_db)) -> CondominiumService:
    return CondominiumService(Repository(db, Condominium), Repository(db, PBX))


def get_trunk_service(db: AsyncSession = Depends(get_db)) -> TrunkService:
    try:
        cipher = TrunkCredentialCipher(_keys())
    except CredentialConfigurationError as error:
        raise HTTPException(503, detail={"code": "credential_key_unavailable"}) from error
    return TrunkService(
        Repository(db, ATATrunk), Repository(db, Condominium), Repository(db, PBX),
        credential_cipher=cipher,
        legacy_provider=LegacyDirectoryProvider(settings.LEGACY_DIRECTORY_PATH),
    )


def get_trunk_state_service(db: AsyncSession = Depends(get_db)) -> TrunkStateService:
    return TrunkStateService(
        TrunkStateRepository(db), event_bus.redis, TrunkIdentityResolver(db)
    )


def _condominium_view(item) -> CondominiumResponse:
    return CondominiumResponse(
        id=str(item.id), tenant_id=str(item.tenant_id), pbx_id=str(item.pbx_id),
        name=item.name, external_id=item.external_id, enabled=item.enabled,
        created_at=item.created_at, updated_at=item.updated_at,
    )


def _mask_username(username: str) -> str:
    return f"***{username[-4:]}" if len(username) > 4 else "***"


def _trunk_view(item, active_calls: int = 0) -> TrunkResponse:
    return TrunkResponse(
        id=str(item.id), tenant_id=str(item.tenant_id), pbx_id=str(item.pbx_id),
        condominium_id=str(item.condominium_id), prefix=item.prefix,
        auth_username_masked=_mask_username(item.auth_username), sip_profile=item.sip_profile,
        transport=item.transport, enabled=item.enabled,
        registration_status=item.registration_status, active_calls=active_calls,
        in_use=active_calls > 0, last_registered_at=item.last_registered_at,
        last_unregistered_at=item.last_unregistered_at, last_error_code=item.last_error_code,
        last_error_at=item.last_error_at,
    )


async def _active_calls_or_zero(
    state_service: TrunkStateService, trunk_id: str
) -> int:
    try:
        return await state_service.active_calls(trunk_id)
    except RedisError:
        logger.exception("trunk_active_calls_unavailable")
        return 0


def _map_service_error(error: Exception):
    if isinstance(error, ScopeValidationError):
        raise HTTPException(404, detail={"code": str(error)}) from error
    if isinstance(error, DuplicateIdentityError):
        raise HTTPException(409, detail={"code": str(error)}) from error
    if isinstance(error, ValueError):
        raise HTTPException(400, detail={"code": str(error)}) from error
    raise error


@router.post("/condominiums", status_code=status.HTTP_201_CREATED, response_model=CondominiumResponse)
async def create_condominium(
    data: CondominiumCreate,
    payload: dict = Depends(require_admin_role),
    service: CondominiumService = Depends(get_condominium_service),
):
    try:
        item = await service.create(payload["tenant_id"], data.pbx_id, data.name, data.external_id, data.enabled)
        return _condominium_view(item)
    except ValueError as error:
        _map_service_error(error)


@router.get("/condominiums", response_model=list[CondominiumResponse])
async def list_condominiums(
    pbx_id: str | None = None,
    payload: dict = Depends(require_admin_role),
    service: CondominiumService = Depends(get_condominium_service),
):
    return [_condominium_view(item) for item in await service.list(payload["tenant_id"], pbx_id)]


@router.patch("/condominiums/{condominium_id}", response_model=CondominiumResponse)
async def update_condominium(
    condominium_id: str,
    data: CondominiumUpdate,
    payload: dict = Depends(require_admin_role),
    service: CondominiumService = Depends(get_condominium_service),
):
    try:
        item = await service.update(
            payload["tenant_id"], condominium_id, **data.model_dump(exclude_unset=True)
        )
        return _condominium_view(item)
    except ValueError as error:
        _map_service_error(error)


@router.post("/trunks", status_code=status.HTTP_201_CREATED, response_model=TrunkResponse)
async def create_trunk(
    data: TrunkCreate,
    payload: dict = Depends(require_admin_role),
    service: TrunkService = Depends(get_trunk_service),
    state_service: TrunkStateService = Depends(get_trunk_state_service),
):
    try:
        item = await service.create(tenant_id=payload["tenant_id"], **data.model_dump())
        active_calls = await _active_calls_or_zero(state_service, str(item.id))
        return _trunk_view(item, active_calls)
    except ValueError as error:
        _map_service_error(error)


@router.get("/trunks", response_model=list[TrunkResponse])
async def list_trunks(
    pbx_id: str | None = None,
    condominium_id: str | None = None,
    enabled: bool | None = None,
    registration_status: str | None = None,
    sip_profile: str | None = None,
    payload: dict = Depends(require_admin_role),
    service: TrunkService = Depends(get_trunk_service),
    state_service: TrunkStateService = Depends(get_trunk_state_service),
):
    items = await service.list(
        payload["tenant_id"], pbx_id=pbx_id, condominium_id=condominium_id,
        enabled=enabled, registration_status=registration_status, sip_profile=sip_profile,
    )
    active_counts = await asyncio.gather(*(
        _active_calls_or_zero(state_service, str(item.id)) for item in items
    ))
    return [_trunk_view(item, count) for item, count in zip(items, active_counts)]


@router.patch("/trunks/{trunk_id}", response_model=TrunkResponse)
async def update_trunk(
    trunk_id: str,
    data: TrunkUpdate,
    payload: dict = Depends(require_admin_role),
    service: TrunkService = Depends(get_trunk_service),
    state_service: TrunkStateService = Depends(get_trunk_state_service),
):
    try:
        item = await service.update(
            payload["tenant_id"], trunk_id, **data.model_dump(exclude_unset=True)
        )
        active_calls = await _active_calls_or_zero(state_service, str(item.id))
        return _trunk_view(item, active_calls)
    except ValueError as error:
        _map_service_error(error)


@router.post("/trunks/import")
async def import_trunks(
    pbx_id: str,
    dry_run: bool = Query(True),
    file: UploadFile = File(...),
    payload: dict = Depends(require_admin_role),
    service: TrunkService = Depends(get_trunk_service),
):
    content = await file.read(5 * 1024 * 1024 + 1)
    try:
        return await import_trunk_csv(
            content, payload["tenant_id"], pbx_id, dry_run=dry_run, trunk_service=service
        )
    except CSVSchemaError as error:
        code = str(error)
        http_status = 413 if code == "csv_too_large" else 422
        raise HTTPException(http_status, detail={"code": code}) from error
