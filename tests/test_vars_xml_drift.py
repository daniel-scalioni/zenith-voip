"""Smoke test de drift: freeswitch/conf/vars.xml vs Postgres (GAP-RE-07).

Só roda com ZENITH_RUN_INFRA_TESTS=1 (mesmo padrão de test_infra.py), pois
exige o Postgres real do stack de integração. Falha se vars.xml não refletir
o Tenant/PBX do schema configurado — sinal de que alguém editou vars.xml à
mão sem rodar scripts/sync_vars_xml.py.

Nenhum container do docker-compose atual tem os dois pré-requisitos ao mesmo
tempo: `vars.xml` só está montado em `freeswitch` (que não tem Python/rede
pro Postgres); o Postgres só é alcançável a partir de `fastapi-*`/`arq-*`
(que não montam `freeswitch/conf`). Para rodar de verdade, bridgeie o
arquivo manualmente antes (mesmo procedimento usado para validar GAP-RE-07
em produção, 2026-08-23):

    docker compose exec <serviço-com-rede-pg> \
        env ZENITH_VARS_XML_PATH=/tmp/vars.xml pytest tests/test_vars_xml_drift.py

com `/tmp/vars.xml` copiado pra dentro do container via `docker compose cp`
antes. Sem esse bridge manual, este teste é pulado
(ZENITH_RUN_INFRA_TESTS != 1) ou falha com FileNotFoundError, não com o
resultado de divergência que o nome sugere — não é um smoke test que roda
sozinho em nenhum pipeline hoje (este projeto não tem CI configurado).
"""
import importlib.util
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
VARS_XML_SCHEMA = os.getenv("ZENITH_VARS_XML_SCHEMA", "tenant_akom")
VARS_XML_PATH = Path(
    os.getenv("ZENITH_VARS_XML_PATH", str(PROJECT_ROOT / "freeswitch" / "conf" / "vars.xml"))
)


def _load_sync_vars_xml():
    spec = importlib.util.spec_from_file_location(
        "zenith_sync_vars_xml", PROJECT_ROOT / "scripts" / "sync_vars_xml.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_vars_xml_matches_postgres_for_configured_tenant():
    # Arrange
    sync_vars_xml = _load_sync_vars_xml()

    # Act
    diverged = await sync_vars_xml.sync(VARS_XML_SCHEMA, VARS_XML_PATH, check_only=True)

    # Assert
    assert not diverged, (
        f"{VARS_XML_PATH} está divergente do Postgres para {VARS_XML_SCHEMA} — "
        "rode scripts/sync_vars_xml.py para corrigir"
    )
