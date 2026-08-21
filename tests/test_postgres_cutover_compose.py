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

    # Assert
    assert postgres["container_name"] == "zenith-postgres-candidate"
    assert "ai-hub-net" in postgres["networks"]
    assert "zenith_postgres_candidate_data:/var/lib/postgresql/data" in postgres["volumes"]
    assert infra["volumes"]["zenith_postgres_candidate_data"] == {
        "name": "zenith-postgres-candidate-data",
        "external": True,
    }
    assert "POSTGRES_USER=zenith_candidate" in postgres["environment"]
    assert "POSTGRES_DB=zenith_candidate" in postgres["environment"]
    assert (
        "POSTGRES_PASSWORD=${ZENITH_CANDIDATE_POSTGRES_PASSWORD:?defina "
        "ZENITH_CANDIDATE_POSTGRES_PASSWORD}"
    ) in postgres["environment"]
    assert database_urls
    assert all(
        url == "DATABASE_URL=${DATABASE_URL:?defina DATABASE_URL com a senha URL-encoded}"
        for url in database_urls
    )
