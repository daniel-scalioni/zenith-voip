from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _compose(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text())


def test_canonical_compose_preserves_promoted_postgres_cutover():
    # Arrange
    infra = _compose("docker-compose.infra.yml")
    app = _compose("docker-compose.app.yml")
    postgres = infra["services"]["postgres"]

    # Act
    database_urls = [
        value
        for service in app["services"].values()
        for value in service.get("environment", [])
        if isinstance(value, str) and value.startswith("DATABASE_URL=")
    ]

    # Assert — nome canônico pós-ADR-012 (legado zenith-postgres removido, sem colisão possível)
    assert postgres["container_name"] == "zenith-postgres"
    assert "ai-hub-net" in postgres["networks"]
    assert "zenith_postgres_data:/var/lib/postgresql/data" in postgres["volumes"]
    assert infra["volumes"]["zenith_postgres_data"] == {
        "name": "zenith-postgres-data",
        "external": True,
    }
    # GAP-31 (2026-08-24): POSTGRES_USER/DB aqui tinham ficado em "zenith_candidate" — resíduo
    # de antes do rename do ADR-012. Isso é só o bootstrap do initdb (sem efeito em volume já
    # populado), mas causou dessincronia real: numa reinicialização de volume vazio, o cluster
    # teria sido inicializado com um role/banco diferente do que o DATABASE_URL da aplicação
    # espera (zenith/zenith) — e de fato foi o que aconteceu em produção em 2026-08-20 quando o
    # volume foi recriado, gerando um role/banco "zenith_candidate" órfão e superusuário, sem
    # nenhuma consumidora, com dados legados obsoletos (mesma assinatura do GAP-28: 12 chamadas
    # até 2026-08-01, 0 transcrições). Este teste antes afirmava o valor errado como esperado —
    # por isso a dessincronia nunca foi pega. Corrigido para bater com o DATABASE_URL real.
    assert "POSTGRES_USER=zenith" in postgres["environment"]
    assert "POSTGRES_DB=zenith" in postgres["environment"]
    assert (
        "POSTGRES_PASSWORD=${ZENITH_POSTGRES_PASSWORD:?defina "
        "ZENITH_POSTGRES_PASSWORD}"
    ) in postgres["environment"]
    assert postgres["healthcheck"]["test"] == ["CMD-SHELL", "pg_isready -U zenith -d zenith"]
    assert database_urls
    assert all(
        url == "DATABASE_URL=${DATABASE_URL:?defina DATABASE_URL com a senha URL-encoded}"
        for url in database_urls
    )
