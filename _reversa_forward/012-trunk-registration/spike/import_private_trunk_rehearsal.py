"""Importa um tronco privado no rehearsal e imprime somente evidência sanitizada."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.database.models import ATATrunk, Condominium, PBX
from src.services.base import Repository
from src.services.legacy_directory import LegacyDirectoryProvider
from src.services.trunk_credentials import TrunkCredentialCipher
from src.services.trunk_import import import_trunk_json
from src.services.trunks import CondominiumService, TrunkService


async def run(args) -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            condominiums = Repository(session, Condominium)
            pbxs = Repository(session, PBX)
            trunks = Repository(session, ATATrunk)
            condominium = await CondominiumService(condominiums, pbxs).create(
                args.tenant_id,
                args.pbx_id,
                args.condominium_name,
                args.condominium_external_id,
            )
            service = TrunkService(
                trunks,
                condominiums,
                pbxs,
                credential_cipher=TrunkCredentialCipher(
                    [os.environ["TRUNK_CREDENTIAL_KEY"]]
                ),
                legacy_provider=LegacyDirectoryProvider("/nonexistent/extensions.xml"),
            )
            result = await import_trunk_json(
                Path(args.input).read_bytes(),
                args.tenant_id,
                args.pbx_id,
                condominium_name=args.condominium_name,
                condominium_id=str(condominium.id),
                dry_run=False,
                trunk_service=service,
            )
            trunk = (await trunks.find_by(
                sip_profile="internal-7060", auth_username="1020"
            ))[0]
            print(json.dumps({
                "created": result.created,
                "updated": result.updated,
                "unchanged": result.unchanged,
                "condominium": condominium.name,
                "trunk_id": str(trunk.id),
                "auth_username": trunk.auth_username,
                "sip_profile": trunk.sip_profile,
                "prefix": trunk.prefix,
                "enabled": trunk.enabled,
                "credential_encrypted": bool(trunk.encrypted_password),
            }, ensure_ascii=False, sort_keys=True))
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--pbx-id", required=True)
    parser.add_argument("--condominium-name", required=True)
    parser.add_argument("--condominium-external-id", required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
