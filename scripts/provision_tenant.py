#!/usr/bin/env python3
"""
Provisiona um novo tenant: cria a linha em public.tenants, a linha do PBX em
public.pbxs, e o schema PostgreSQL dedicado do tenant (schema-per-tenant,
ADR-001) com as tabelas de Call/Transcript/CallInsight/STTMetric.

Usa create_tenant_schema() (SQLAlchemy metadata.create_all), não Alembic:
as migrations 001 e 003 criam tabelas com o mesmo nome sem qualificar schema
explicitamente, então rodar `alembic upgrade head` contra um schema de tenant
colide (001 cria "calls" no search_path, 003 tenta criar "calls" de novo e
falha). create_tenant_schema() evita esse problema criando só as tabelas de
TenantBase (o design real de 003), direto.

Uso:
    python3 scripts/provision_tenant.py --name "Akom" --schema tenant_akom \
        --pbx-name "VitalPBX Akom" --pbx-host sip.maisalerta.tecnorise.com --pbx-port 7060

Após rodar, use o "tenant_id" impresso (o slug depois de "tenant_", ex: "akom")
em freeswitch/conf/vars.xml como tenant_id=<slug>, e o UUID do PBX como pbx_id
— ou passe --sync-vars-xml PATH para escrever isso automaticamente a partir do
Postgres (GAP-RE-07). Opt-in: sem a flag, nada em vars.xml é tocado.
"""
import argparse
import asyncio
import importlib.util
import sys
import uuid
from pathlib import Path

sys.path.insert(0, ".")

from src.database.database import async_session_factory, create_tenant_schema
from src.database.models import Tenant, PBX
from sqlalchemy import delete, select


def _load_sync_vars_xml():
    spec = importlib.util.spec_from_file_location(
        "zenith_sync_vars_xml", Path(__file__).parent / "sync_vars_xml.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _validate_restore_ids(
    tenant_id: uuid.UUID | None, pbx_id: uuid.UUID | None, restore: bool
) -> tuple[uuid.UUID, uuid.UUID]:
    supplied = tenant_id is not None or pbx_id is not None
    if supplied and not restore:
        raise ValueError("UUIDs explícitos só são permitidos no modo restore")
    if restore and (tenant_id is None or pbx_id is None):
        raise ValueError("restore exige tenant_id e pbx_id explícitos")
    return tenant_id or uuid.uuid4(), pbx_id or uuid.uuid4()


async def provision(
    name: str,
    schema_name: str,
    pbx_name: str,
    pbx_host: str,
    pbx_port: int,
    *,
    tenant_id: uuid.UUID | None = None,
    pbx_id: uuid.UUID | None = None,
    restore: bool = False,
    sync_vars_xml_path: Path | None = None,
):
    if not schema_name.startswith("tenant_"):
        raise ValueError('schema_name deve começar com "tenant_" (convenção do projeto)')
    slug = schema_name.removeprefix("tenant_")
    if not slug.isalnum():
        raise ValueError(
            f'O slug "{slug}" precisa ser alfanumérico simples (sem hífen/underscore) — '
            f'_tenant_schema() monta a query SQL como f"tenant_{{tenant_id}}" sem aspas.'
        )

    resolved_tenant_id, resolved_pbx_id = _validate_restore_ids(tenant_id, pbx_id, restore)
    tenant_created = False
    pbx_created = False

    async with async_session_factory() as session:
        try:
            existing = await session.scalar(
                select(Tenant).where(Tenant.schema_name == schema_name)
            )
            if existing:
                if restore and existing.id != resolved_tenant_id:
                    raise ValueError("conflito de UUID do tenant durante restore")
                resolved_tenant_id = existing.id
                print(
                    f"Tenant já existe: id={existing.id} name={existing.name} "
                    f"schema={existing.schema_name}"
                )
            else:
                tenant = Tenant(
                    id=resolved_tenant_id, name=name, schema_name=schema_name
                )
                session.add(tenant)
                await session.commit()
                tenant_created = True
                await session.refresh(tenant)
                print(
                    f"Tenant criado: id={resolved_tenant_id} name={name} "
                    f"schema={schema_name}"
                )

            existing_pbx = await session.scalar(
                select(PBX).where(
                    PBX.tenant_id == resolved_tenant_id,
                    PBX.host == pbx_host,
                    PBX.port == pbx_port,
                )
            )
            if existing_pbx:
                if restore and existing_pbx.id != resolved_pbx_id:
                    raise ValueError("conflito de UUID do PBX durante restore")
                resolved_pbx_id = existing_pbx.id
                print(
                    f"PBX já existe: id={existing_pbx.id} "
                    f"host={pbx_host}:{pbx_port}"
                )
            else:
                pbx = PBX(
                    id=resolved_pbx_id,
                    tenant_id=resolved_tenant_id,
                    name=pbx_name,
                    host=pbx_host,
                    port=pbx_port,
                )
                session.add(pbx)
                await session.commit()
                pbx_created = True
                await session.refresh(pbx)
                print(
                    f"PBX criado: id={resolved_pbx_id} host={pbx_host}:{pbx_port}"
                )

            await create_tenant_schema(schema_name)
        except BaseException:
            await session.rollback()
            # Os commits intermediários tornam os UUIDs disponíveis para logs e
            # integrações, mas exigem compensação para manter o provisionamento
            # atomicamente observável quando uma etapa posterior falha.
            if pbx_created:
                await session.scalar(delete(PBX).where(PBX.id == resolved_pbx_id).returning(PBX.id))
            if tenant_created:
                await session.scalar(
                    delete(Tenant).where(Tenant.id == resolved_tenant_id).returning(Tenant.id)
                )
            if pbx_created or tenant_created:
                await session.commit()
            raise

    print(f"Schema '{schema_name}' criado/confirmado com as tabelas de Call/Transcript/CallInsight/STTMetric.")

    print("\n--- Adicione em freeswitch/conf/vars.xml ---")
    print(f'  <X-PRE-PROCESS cmd="set" data="tenant_id={slug}"/>')
    print(f'  <X-PRE-PROCESS cmd="set" data="pbx_id={resolved_pbx_id}"/>')

    if sync_vars_xml_path is not None:
        sync_vars_xml = _load_sync_vars_xml()
        changed = await sync_vars_xml.sync(schema_name, sync_vars_xml_path, check_only=False)
        if changed:
            print(f"\n{sync_vars_xml_path} atualizado automaticamente (--sync-vars-xml).")
        else:
            print(f"\n{sync_vars_xml_path} já estava sincronizado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help='Nome do tenant, ex: "Akom"')
    parser.add_argument("--schema", required=True, help='schema_name, ex: "tenant_akom" (deve começar com tenant_)')
    parser.add_argument("--pbx-name", required=True, help='Nome do PBX, ex: "VitalPBX Akom"')
    parser.add_argument("--pbx-host", required=True, help="Host do PBX, ex: sip.maisalerta.tecnorise.com")
    parser.add_argument("--pbx-port", type=int, default=5060, help="Porta do PBX (default 5060)")
    parser.add_argument("--tenant-id", type=uuid.UUID, help="UUID preservado no modo restore")
    parser.add_argument("--pbx-id", type=uuid.UUID, help="UUID preservado no modo restore")
    parser.add_argument("--restore", action="store_true", help="Preservar UUIDs durante restore")
    parser.add_argument(
        "--sync-vars-xml",
        type=Path,
        default=None,
        help=(
            "Opt-in: escreve tenant_id/pbx_id neste vars.xml automaticamente "
            "(GAP-RE-07). Sem esta flag, só imprime as instruções manuais."
        ),
    )
    args = parser.parse_args()

    asyncio.run(
        provision(
            args.name,
            args.schema,
            args.pbx_name,
            args.pbx_host,
            args.pbx_port,
            tenant_id=args.tenant_id,
            pbx_id=args.pbx_id,
            restore=args.restore,
            sync_vars_xml_path=args.sync_vars_xml,
        )
    )
