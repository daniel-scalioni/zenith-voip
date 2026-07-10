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
em freeswitch/conf/vars.xml como tenant_id=<slug>, e o UUID do PBX como pbx_id.
"""
import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from src.database.database import async_session_factory, create_tenant_schema
from src.database.models import Tenant, PBX
from sqlalchemy import select


async def provision(name: str, schema_name: str, pbx_name: str, pbx_host: str, pbx_port: int):
    if not schema_name.startswith("tenant_"):
        raise ValueError('schema_name deve começar com "tenant_" (convenção do projeto)')
    slug = schema_name.removeprefix("tenant_")
    if not slug.isalnum():
        raise ValueError(
            f'O slug "{slug}" precisa ser alfanumérico simples (sem hífen/underscore) — '
            f'_tenant_schema() monta a query SQL como f"tenant_{{tenant_id}}" sem aspas.'
        )

    async with async_session_factory() as session:
        existing = await session.scalar(select(Tenant).where(Tenant.schema_name == schema_name))
        if existing:
            print(f"Tenant já existe: id={existing.id} name={existing.name} schema={existing.schema_name}")
            tenant_id = existing.id
        else:
            tenant = Tenant(name=name, schema_name=schema_name)
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            tenant_id = tenant.id
            print(f"Tenant criado: id={tenant_id} name={name} schema={schema_name}")

        existing_pbx = await session.scalar(
            select(PBX).where(PBX.tenant_id == tenant_id, PBX.host == pbx_host, PBX.port == pbx_port)
        )
        if existing_pbx:
            print(f"PBX já existe: id={existing_pbx.id} host={pbx_host}:{pbx_port}")
            pbx_id = existing_pbx.id
        else:
            pbx = PBX(tenant_id=tenant_id, name=pbx_name, host=pbx_host, port=pbx_port)
            session.add(pbx)
            await session.commit()
            await session.refresh(pbx)
            pbx_id = pbx.id
            print(f"PBX criado: id={pbx_id} host={pbx_host}:{pbx_port}")

    await create_tenant_schema(schema_name)
    print(f"Schema '{schema_name}' criado/confirmado com as tabelas de Call/Transcript/CallInsight/STTMetric.")

    print("\n--- Adicione em freeswitch/conf/vars.xml ---")
    print(f'  <X-PRE-PROCESS cmd="set" data="tenant_id={slug}"/>')
    print(f'  <X-PRE-PROCESS cmd="set" data="pbx_id={pbx_id}"/>')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help='Nome do tenant, ex: "Akom"')
    parser.add_argument("--schema", required=True, help='schema_name, ex: "tenant_akom" (deve começar com tenant_)')
    parser.add_argument("--pbx-name", required=True, help='Nome do PBX, ex: "VitalPBX Akom"')
    parser.add_argument("--pbx-host", required=True, help="Host do PBX, ex: sip.maisalerta.tecnorise.com")
    parser.add_argument("--pbx-port", type=int, default=5060, help="Porta do PBX (default 5060)")
    args = parser.parse_args()

    asyncio.run(provision(args.name, args.schema, args.pbx_name, args.pbx_host, args.pbx_port))
