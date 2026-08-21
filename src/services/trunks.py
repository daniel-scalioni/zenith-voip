"""Regras tenant-scoped para condomínios e troncos ATA."""

import inspect
import re
from typing import Any

from src.services.base import IntegrityConstraintError


class ScopeValidationError(ValueError):
    pass


class DuplicateIdentityError(ValueError):
    pass


def _translate_trunk_integrity_error(error: IntegrityConstraintError) -> Exception:
    message = str(error).lower()
    if "ck_ata_trunks_prefix_digits" in message:
        return ValueError("invalid_prefix")
    if "uq_ata_trunks_tenant_prefix" in message:
        return DuplicateIdentityError("duplicate_prefix")
    if "fkey" in message or "foreign key" in message:
        return ScopeValidationError("condominium_not_found")
    return DuplicateIdentityError("duplicate_auth_identity")


async def _resolve(value):
    return await value if inspect.isawaitable(value) else value


def _first(result):
    if result is None:
        return None
    if isinstance(result, (list, tuple)):
        return result[0] if result else None
    return result


class CondominiumService:
    def __init__(self, condominium_repository, pbx_repository):
        self._condominiums = condominium_repository
        self._pbxs = pbx_repository

    async def create(
        self,
        tenant_id: str,
        pbx_id: str,
        name: str,
        external_id: str | None = None,
        enabled: bool = True,
    ):
        pbx = await self._pbxs.get(pbx_id)
        if pbx is None or str(pbx.tenant_id) != str(tenant_id):
            raise ScopeValidationError("pbx_not_found")
        existing = _first(await self._condominiums.find_by(
            tenant_id=tenant_id, pbx_id=pbx_id, name=name
        ))
        if existing is not None:
            return existing
        try:
            return await self._condominiums.create(
                tenant_id=tenant_id,
                pbx_id=pbx_id,
                name=name,
                external_id=external_id,
                enabled=enabled,
            )
        except IntegrityConstraintError as error:
            raise DuplicateIdentityError("duplicate_external_id") from error

    async def list(self, tenant_id: str, pbx_id: str | None = None):
        filters = {"tenant_id": tenant_id}
        if pbx_id is not None:
            filters["pbx_id"] = pbx_id
        return await self._condominiums.find_by(**filters)

    async def update(self, tenant_id: str, condominium_id: str, **changes):
        condominium = await self._condominiums.get(condominium_id)
        if condominium is None or str(condominium.tenant_id) != str(tenant_id):
            raise ScopeValidationError("condominium_not_found")
        allowed = {key: value for key, value in changes.items() if key in {"name", "external_id", "enabled"}}
        try:
            return await self._condominiums.update(condominium_id, **allowed)
        except IntegrityConstraintError as error:
            raise DuplicateIdentityError("duplicate_external_id") from error


class TrunkService:
    def __init__(
        self,
        trunk_repository,
        condominium_repository,
        pbx_repository,
        *,
        credential_cipher,
        legacy_provider,
        tenant_repository=None,
    ):
        self._trunks = trunk_repository
        self._condominiums = condominium_repository
        self._pbxs = pbx_repository
        self._cipher = credential_cipher
        self._legacy = legacy_provider
        self._tenants = tenant_repository

    async def _validate_scope(self, tenant_id: str, pbx_id: str, condominium_id: str):
        pbx = await self._pbxs.get(pbx_id)
        condominium = await self._condominiums.get(condominium_id)
        if pbx is None or str(pbx.tenant_id) != str(tenant_id):
            raise ScopeValidationError("pbx_not_found")
        if (
            condominium is None
            or str(condominium.tenant_id) != str(tenant_id)
            or str(condominium.pbx_id) != str(pbx_id)
        ):
            raise ScopeValidationError("condominium_not_found")
        return condominium

    async def _ensure_unique(
        self,
        tenant_id: str,
        prefix: str | None,
        sip_profile: str,
        auth_username: str,
    ):
        identity = _first(await self._trunks.find_by(
            sip_profile=sip_profile, auth_username=auth_username
        ))
        if identity is not None:
            raise DuplicateIdentityError("duplicate_auth_identity")
        if prefix is not None:
            duplicate_prefix = _first(
                await self._trunks.find_by(tenant_id=tenant_id, prefix=prefix)
            )
            if duplicate_prefix is not None:
                raise DuplicateIdentityError("duplicate_prefix")
        if await _resolve(self._legacy.contains(sip_profile, auth_username)):
            raise DuplicateIdentityError("duplicate_auth_identity")

    async def _validate_create_inputs(
        self,
        tenant_id: str,
        pbx_id: str,
        condominium_id: str,
        prefix: str | None,
        auth_username: str,
        password: str,
        sip_profile: str,
        transport: str,
    ):
        await self._validate_scope(tenant_id, pbx_id, condominium_id)
        if prefix is not None and not re.fullmatch(r"[0-9]{1,32}", prefix):
            raise ValueError("invalid_prefix")
        if not password or not password.strip():
            raise ValueError("invalid_password")
        if sip_profile not in {"internal", "internal-7060"} or transport != "udp":
            raise ValueError("invalid_sip_configuration")
        await self._ensure_unique(tenant_id, prefix, sip_profile, auth_username)

    async def validate_importable(self, *, tenant_id: str, pbx_id: str, row):
        """Valida se upsert_imported(row) teria sucesso, sem persistir nada.

        Usado pelo pré-voo tudo-ou-nada da importação em lote (design.md#Importação
        VitalPBX Exportada): qualquer item inválido precisa rejeitar o lote inteiro
        antes da primeira escrita, não no meio dela.
        """
        identity = {"sip_profile": row.sip_profile, "auth_username": row.auth_username}
        existing = _first(await self._trunks.find_by(**identity))
        if existing is not None:
            if str(existing.tenant_id) != str(tenant_id):
                raise ScopeValidationError("trunk_not_found")
            if row.password is not None and not row.password.strip():
                raise ValueError("invalid_password")
            return
        await self._validate_create_inputs(
            tenant_id, pbx_id, row.condominium_id, row.prefix,
            row.auth_username, row.password, row.sip_profile, "udp",
        )

    async def create(
        self,
        *,
        tenant_id: str,
        pbx_id: str,
        condominium_id: str,
        prefix: str | None = None,
        auth_username: str,
        password: str,
        sip_profile: str,
        enabled: bool = False,
        transport: str = "udp",
    ):
        await self._validate_create_inputs(
            tenant_id, pbx_id, condominium_id, prefix, auth_username, password, sip_profile, transport,
        )
        encrypted_password = await _resolve(self._cipher.encrypt(password))
        try:
            return await self._trunks.create(
                tenant_id=tenant_id,
                pbx_id=pbx_id,
                condominium_id=condominium_id,
                prefix=prefix,
                auth_username=auth_username,
                encrypted_password=encrypted_password,
                sip_profile=sip_profile,
                transport=transport,
                enabled=enabled,
                registration_status="unknown",
            )
        except IntegrityConstraintError as error:
            raise _translate_trunk_integrity_error(error) from error

    async def update(self, tenant_id: str, trunk_id: str, **changes):
        trunk = await self._trunks.get(trunk_id)
        if trunk is None or str(trunk.tenant_id) != str(tenant_id):
            raise ScopeValidationError("trunk_not_found")
        allowed_names = {"condominium_id", "prefix", "auth_username", "sip_profile", "enabled"}
        updates = {key: value for key, value in changes.items() if key in allowed_names}
        new_condominium_id = updates.get("condominium_id", trunk.condominium_id)
        if str(new_condominium_id) != str(trunk.condominium_id):
            await self._validate_scope(tenant_id, str(trunk.pbx_id), str(new_condominium_id))

        new_prefix = updates.get("prefix", getattr(trunk, "prefix", None))
        if new_prefix is not None and not re.fullmatch(r"[0-9]{1,32}", new_prefix):
            raise ValueError("invalid_prefix")
        new_auth_username = updates.get("auth_username", trunk.auth_username)
        new_sip_profile = updates.get("sip_profile", trunk.sip_profile)
        if not new_auth_username or new_sip_profile not in {"internal", "internal-7060"}:
            raise ValueError("invalid_sip_configuration")

        sip_identity_changed = any(
            key in updates and str(updates[key]) != str(getattr(trunk, key))
            for key in {"auth_username", "sip_profile"}
        )
        if sip_identity_changed:
            existing = _first(await self._trunks.find_by(
                sip_profile=new_sip_profile, auth_username=new_auth_username
            ))
            if existing is not None and str(existing.id) != str(trunk.id):
                raise DuplicateIdentityError("duplicate_auth_identity")
            if await _resolve(self._legacy.contains(new_sip_profile, new_auth_username)):
                raise DuplicateIdentityError("duplicate_auth_identity")

        identity_changed = sip_identity_changed
        password = changes.get("password")
        if password is not None:
            if not password or not password.strip():
                raise ValueError("invalid_password")
            updates["encrypted_password"] = await _resolve(self._cipher.encrypt(password))
            identity_changed = True
        if identity_changed:
            updates["registration_status"] = "unknown"
            updates["last_registered_at"] = None
            updates["last_unregistered_at"] = None
        try:
            return await self._trunks.update(trunk_id, **updates)
        except IntegrityConstraintError as error:
            raise _translate_trunk_integrity_error(error) from error

    async def list(self, tenant_id: str, **filters):
        scoped = {"tenant_id": tenant_id}
        scoped.update({key: value for key, value in filters.items() if value is not None})
        return await self._trunks.find_by(**scoped)

    async def lookup_directory_identity(self, sip_profile: str, auth_username: str):
        trunk = _first(await self._trunks.find_by(
            sip_profile=sip_profile, auth_username=auth_username
        ))
        if trunk is None or not trunk.enabled:
            return None
        condominium = await self._condominiums.get(trunk.condominium_id)
        pbx = await self._pbxs.get(trunk.pbx_id)
        if condominium is None or not condominium.enabled or pbx is None:
            return None
        if (
            str(condominium.tenant_id) != str(trunk.tenant_id)
            or str(condominium.pbx_id) != str(trunk.pbx_id)
            or str(pbx.tenant_id) != str(trunk.tenant_id)
        ):
            return None
        if self._tenants is not None:
            tenant = await self._tenants.get(trunk.tenant_id)
            if tenant is None or tenant.status != "active":
                return None
        return trunk

    async def upsert_imported(self, *, tenant_id: str, pbx_id: str, row):
        identity = {"sip_profile": row.sip_profile, "auth_username": row.auth_username}
        existing = _first(await self._trunks.find_by(**identity))
        if existing is not None:
            changes = {
                "auth_username": row.auth_username,
                "password": row.password,
                "sip_profile": row.sip_profile,
                "enabled": False,
            }
            await self.update(tenant_id, str(existing.id), **changes)
            return "updated"
        await self.create(
            tenant_id=tenant_id,
            pbx_id=pbx_id,
            condominium_id=row.condominium_id,
            prefix=row.prefix,
            auth_username=row.auth_username,
            password=row.password,
            sip_profile=row.sip_profile,
            enabled=False,
        )
        return "created"
