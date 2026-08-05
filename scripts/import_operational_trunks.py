"""Importa troncos ATA do veículo de exportação VitalPBX lendo o JSON de stdin.

O arquivo com credenciais nunca é gravado no host de deploy: o conteúdo entra por
stdin, é usado em memória e descartado. A saída é sanitizada — só contagens e
identificadores públicos, jamais senha, chave ou o documento bruto.

Uso:
    docker run --rm -i ... python scripts/import_operational_trunks.py \
        --tenant-id <uuid> --pbx-id <uuid> \
        --map 1020="Parque Portugal" --map 1780=Camboriu [--apply]
    < export_extension_trunks.json

Sem --apply o script faz apenas dry-run: valida, não cifra e não persiste.
"""

import argparse
import asyncio
import sys

from src.database.database import async_session_factory
from src.database.models import ATATrunk, Condominium, PBX
from src.services.base import Repository
from src.services.legacy_directory import LegacyDirectoryProvider
from src.services.trunk_credentials import TrunkCredentialCipher
from src.services.trunk_import import import_trunk_json_batch
from src.services.trunks import CondominiumService, TrunkService
from src.config import settings


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--pbx-id", required=True)
    parser.add_argument(
        "--map",
        action="append",
        required=True,
        metavar="NUMERO=CONDOMINIO",
        help="Mapa explícito identidade SIP → condomínio. Repetir por tronco.",
    )
    parser.add_argument("--apply", action="store_true", help="Persiste; sem isso é dry-run.")
    args = parser.parse_args(argv)
    args.condominium_names = dict(item.split("=", 1) for item in args.map)
    return args


def _credential_keys() -> list[str]:
    return [item.strip() for item in settings.TRUNK_CREDENTIAL_KEYS.split(",") if item.strip()]


async def _run(args, content: bytes) -> int:
    async with async_session_factory() as session:
        condominium_service = CondominiumService(
            Repository(session, Condominium), Repository(session, PBX)
        )
        trunk_service = TrunkService(
            Repository(session, ATATrunk),
            Repository(session, Condominium),
            Repository(session, PBX),
            credential_cipher=TrunkCredentialCipher(_credential_keys()),
            legacy_provider=LegacyDirectoryProvider(settings.LEGACY_DIRECTORY_PATH),
        )

        condominium_ids = {}
        for name in dict.fromkeys(args.condominium_names.values()):
            condominium = await condominium_service.create(
                tenant_id=args.tenant_id, pbx_id=args.pbx_id, name=name
            )
            condominium_ids[name] = str(condominium.id)
            print(f"condomínio pronto: {name} -> {condominium.id}")

        result = await import_trunk_json_batch(
            content,
            args.tenant_id,
            args.pbx_id,
            condominium_names=args.condominium_names,
            condominium_ids=condominium_ids,
            dry_run=not args.apply,
            trunk_service=trunk_service,
        )
        if args.apply:
            await session.commit()

        print(
            f"dry_run={result.dry_run} linhas={result.rows} criados={result.created} "
            f"atualizados={result.updated} inalterados={result.unchanged} "
            f"rejeitados={result.rejected}"
        )
        return 0


def main() -> int:
    args = _parse_args(sys.argv[1:])
    content = sys.stdin.buffer.read()
    if not content:
        print("stdin vazio: envie o JSON de exportação por stdin", file=sys.stderr)
        return 2
    return asyncio.run(_run(args, content))


if __name__ == "__main__":
    raise SystemExit(main())
