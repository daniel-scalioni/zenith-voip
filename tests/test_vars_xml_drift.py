"""Smoke test de drift: freeswitch/conf/vars.xml vs Postgres (GAP-RE-07).

Só roda com ZENITH_RUN_INFRA_TESTS=1 (mesmo padrão de test_infra.py), pois
exige o Postgres real do stack de integração. Falha se vars.xml não refletir
o Tenant/PBX do schema configurado — sinal de que alguém editou vars.xml à
mão sem rodar scripts/sync_vars_xml.py.
"""
import importlib.util
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
VARS_XML_SCHEMA = os.getenv("ZENITH_VARS_XML_SCHEMA", "tenant_akom")


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
    vars_xml_path = PROJECT_ROOT / "freeswitch" / "conf" / "vars.xml"

    # Act
    diverged = await sync_vars_xml.sync(VARS_XML_SCHEMA, vars_xml_path, check_only=True)

    # Assert
    assert not diverged, (
        f"{vars_xml_path} está divergente do Postgres para {VARS_XML_SCHEMA} — "
        "rode scripts/sync_vars_xml.py para corrigir"
    )
