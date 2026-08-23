#!/usr/bin/env python3
"""
Gera as linhas tenant_id/pbx_id de freeswitch/conf/vars.xml a partir do Postgres
(Tenant/PBX em public), substituindo a edição manual (GAP-RE-07). Postgres é a
fonte de verdade; vars.xml passa a ser derivado dele.

Limitação intencional: exige exatamente 1 Tenant com o schema_name pedido e
exatamente 1 PBX associado a ele — vars.xml só tem uma variável global por
chave, não há como representar N tenants nele (isso só muda com GAP-PROV-01,
provisionamento dinâmico via mod_xml_curl).

Uso:
    python3 scripts/sync_vars_xml.py --schema tenant_akom
    python3 scripts/sync_vars_xml.py --schema tenant_akom --check
"""
import argparse
import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from sqlalchemy import select

from src.database.database import async_session_factory
from src.database.models import PBX, Tenant

_TENANT_ID_LINE = re.compile(r'(<X-PRE-PROCESS cmd="set" data="tenant_id=)([^"]*)(")')
_PBX_ID_LINE = re.compile(r'(<X-PRE-PROCESS cmd="set" data="pbx_id=)([^"]*)(")')


def render_updated_vars_xml(content: str, tenant_slug: str, pbx_id: str) -> str:
    if not _TENANT_ID_LINE.search(content):
        raise ValueError("vars.xml não tem uma linha tenant_id=... para atualizar")
    if not _PBX_ID_LINE.search(content):
        raise ValueError("vars.xml não tem uma linha pbx_id=... para atualizar")
    content = _TENANT_ID_LINE.sub(rf"\g<1>{tenant_slug}\g<3>", content, count=1)
    content = _PBX_ID_LINE.sub(rf"\g<1>{pbx_id}\g<3>", content, count=1)
    return content


def extract_current_values(content: str) -> tuple[str | None, str | None]:
    tenant_match = _TENANT_ID_LINE.search(content)
    pbx_match = _PBX_ID_LINE.search(content)
    return (
        tenant_match.group(2) if tenant_match else None,
        pbx_match.group(2) if pbx_match else None,
    )


def write_atomic(output: Path, payload: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # vars.xml não é segredo — precisa continuar legível pelo processo do
    # FreeSWITCH depois da troca. mkstemp() cria o temporário em 0600; sem
    # reaplicar o modo original, o replace trocaria silenciosamente as
    # permissões e quebraria o próximo reloadxml/restart.
    mode = output.stat().st_mode if output.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


async def resolve_tenant_pbx(session, schema_name: str) -> tuple[str, str]:
    tenant = await session.scalar(select(Tenant).where(Tenant.schema_name == schema_name))
    if tenant is None:
        raise ValueError(f'Tenant com schema_name="{schema_name}" não encontrado')

    pbxs = (await session.scalars(select(PBX).where(PBX.tenant_id == tenant.id))).all()
    if len(pbxs) != 1:
        raise ValueError(
            f'Tenant "{schema_name}" tem {len(pbxs)} PBX(s) — vars.xml só suporta 1 '
            "global; ambíguo demais para gerar automaticamente"
        )

    slug = schema_name.removeprefix("tenant_")
    return slug, str(pbxs[0].id)


async def sync(schema_name: str, vars_xml_path: Path, *, check_only: bool) -> bool:
    """Retorna True se houve (ou haveria, em check_only) mudança."""
    async with async_session_factory() as session:
        tenant_slug, pbx_id = await resolve_tenant_pbx(session, schema_name)

    content = vars_xml_path.read_text(encoding="utf-8")
    current_tenant, current_pbx = extract_current_values(content)
    changed = current_tenant != tenant_slug or current_pbx != pbx_id

    if not changed or check_only:
        return changed

    write_atomic(vars_xml_path, render_updated_vars_xml(content, tenant_slug, pbx_id))
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--schema", required=True, help='schema_name do tenant, ex: "tenant_akom"')
    parser.add_argument("--vars-xml", type=Path, default=Path("freeswitch/conf/vars.xml"))
    parser.add_argument("--check", action="store_true", help="não escreve, só detecta divergência")
    args = parser.parse_args()

    changed = asyncio.run(sync(args.schema, args.vars_xml, check_only=args.check))

    if args.check:
        if changed:
            print(f"DIVERGENTE: {args.vars_xml} não reflete o Postgres para {args.schema}")
            raise SystemExit(1)
        print(f"OK: {args.vars_xml} já reflete o Postgres para {args.schema}")
        return

    if changed:
        print(f"{args.vars_xml} atualizado a partir do Postgres para {args.schema}")
    else:
        print(f"{args.vars_xml} já estava sincronizado, nada a fazer")


if __name__ == "__main__":
    main()
