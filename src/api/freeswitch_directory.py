"""Callback interno e sanitizado do diretório XML Curl."""

import hmac
import logging
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database.database import get_db
from src.database.models import ATATrunk, Condominium, PBX, Tenant
from src.services.base import Repository
from src.services.legacy_directory import LegacyDirectoryProvider
from src.services.trunk_credentials import (
    CredentialConfigurationError, CredentialTokenError, TrunkCredentialCipher,
)
from src.services.trunks import TrunkService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["internal"])
basic = HTTPBasic(auto_error=False)


class AmbiguousDirectoryIdentityError(ValueError):
    pass


class DirectoryCredentialUnavailableError(ValueError):
    def __init__(self, trunk_id: str = ""):
        self.trunk_id = trunk_id
        super().__init__("credential_key_unavailable")


class DirectoryLookupService:
    def __init__(self, trunk_service: TrunkService, legacy_provider, cipher):
        self._trunks = trunk_service
        self._legacy = legacy_provider
        self._cipher = cipher

    async def lookup(self, profile: str, username: str):
        trunk = await self._trunks.lookup_directory_identity(profile, username)
        legacy = self._legacy.lookup(username)
        if trunk is not None and legacy is not None:
            raise AmbiguousDirectoryIdentityError("directory_identity_ambiguous")
        if trunk is not None:
            try:
                password = self._cipher.decrypt(trunk.encrypted_password)
            except CredentialTokenError as error:
                raise DirectoryCredentialUnavailableError(str(trunk.id)) from error
            return {
                "auth_username": trunk.auth_username,
                "password": password,
                "tenant_id": str(trunk.tenant_id),
                "pbx_id": str(trunk.pbx_id),
                "condominium_id": str(trunk.condominium_id),
                "trunk_id": str(trunk.id),
                "prefix": trunk.prefix,
            }
        if legacy is not None:
            return {
                "auth_username": legacy.username,
                "password": legacy.password,
                "params": legacy.params,
                "variables": legacy.variables,
            }
        return None


def _keys() -> list[str]:
    return [item.strip() for item in settings.TRUNK_CREDENTIAL_KEYS.split(",") if item.strip()]


def get_directory_lookup_service(db: AsyncSession = Depends(get_db)) -> DirectoryLookupService:
    try:
        cipher = TrunkCredentialCipher(_keys())
    except CredentialConfigurationError as error:
        raise HTTPException(503, detail={"code": "credential_key_unavailable"}) from error
    legacy = LegacyDirectoryProvider(settings.LEGACY_DIRECTORY_PATH)
    trunks = TrunkService(
        Repository(db, ATATrunk), Repository(db, Condominium), Repository(db, PBX),
        credential_cipher=cipher, legacy_provider=legacy,
        tenant_repository=Repository(db, Tenant),
    )
    return DirectoryLookupService(trunks, legacy, cipher)


def extract_directory_lookup(form: dict) -> tuple[str, str] | None:
    if form.get("section") != "directory":
        return None
    profile = (
        form.get("sip_profile")
        or form.get("sip_profile_name")
        or form.get("variable_sofia_profile_name")
    )
    username = form.get("sip_auth_username") or form.get("user")
    if not profile or not username:
        return None
    return str(profile), str(username)


def build_directory_xml(domain: str, user: dict) -> str:
    document = ET.Element("document", {"type": "freeswitch/xml"})
    section = ET.SubElement(document, "section", {"name": "directory"})
    domain_element = ET.SubElement(section, "domain", {"name": domain})
    users = ET.SubElement(ET.SubElement(ET.SubElement(domain_element, "groups"), "group", {"name": "default"}), "users")
    user_element = ET.SubElement(users, "user", {"id": user["auth_username"]})
    params = ET.SubElement(user_element, "params")
    supplied_params = user.get("params") or (("password", user["password"]),)
    for name, value in supplied_params:
        ET.SubElement(params, "param", {"name": str(name), "value": str(value)})
    variables = ET.SubElement(user_element, "variables")
    supplied_variables = user.get("variables")
    if supplied_variables is None:
        supplied_variables = [
            ("user_context", "default"),
            ("zenith_tenant_id", user["tenant_id"]),
            ("zenith_pbx_id", user["pbx_id"]),
            ("zenith_condominium_id", user["condominium_id"]),
            ("zenith_trunk_id", user["trunk_id"]),
        ]
        if user.get("prefix") is not None:
            supplied_variables.append(("zenith_trunk_prefix", user["prefix"]))
    for name, value in supplied_variables:
        ET.SubElement(variables, "variable", {"name": str(name), "value": str(value)})
    return ET.tostring(document, encoding="unicode")


def _not_found_xml() -> str:
    return '<document type="freeswitch/xml"><section name="result"><result status="not found"/></section></document>'


def _xml_response(payload: str) -> Response:
    if len(payload.encode("utf-8")) > 65_536:
        payload = _not_found_xml()
    return Response(payload, media_type="application/xml", headers={"Cache-Control": "no-store"})


def _authenticated(credentials: HTTPBasicCredentials | None) -> bool:
    if credentials is None:
        return False
    return hmac.compare_digest(credentials.username, settings.FREESWITCH_DIRECTORY_BASIC_USERNAME) and hmac.compare_digest(
        credentials.password, settings.FREESWITCH_DIRECTORY_BASIC_PASSWORD
    )


@router.post("/internal/freeswitch/directory")
async def freeswitch_directory(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(basic),
    service: DirectoryLookupService = Depends(get_directory_lookup_service),
):
    if not _authenticated(credentials):
        raise HTTPException(401, detail={"code": "unauthorized"}, headers={"WWW-Authenticate": "Basic"})
    form = dict(await request.form())
    lookup = extract_directory_lookup(form)
    if lookup is None:
        return _xml_response(_not_found_xml())
    profile, username = lookup
    try:
        user = await service.lookup(profile, username)
    except AmbiguousDirectoryIdentityError:
        logger.warning("directory_lookup_ambiguous profile=%s", profile)
        return _xml_response(_not_found_xml())
    except DirectoryCredentialUnavailableError as error:
        logger.error("directory_credential_unavailable trunk_id=%s", error.trunk_id)
        raise HTTPException(503, detail={"code": "credential_key_unavailable"}) from error
    if user is None:
        return _xml_response(_not_found_xml())
    domain = form.get("domain") or form.get("key_value") or "zenith.local"
    return _xml_response(build_directory_xml(str(domain), user))
