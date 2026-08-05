"""Parser sanitizado e executor idempotente de CSV de troncos ATA."""

import csv
import io
import json
from dataclasses import dataclass, field, replace


class CSVSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class TrunkCSVRow:
    line: int
    prefix: str | None
    condominium_name: str
    auth_username: str
    password: str = field(repr=False)
    sip_profile: str = "internal"
    condominium_id: str | None = None


@dataclass(frozen=True)
class ParsedTrunkCSV:
    rows: list[TrunkCSVRow]
    ignored: int


@dataclass
class TrunkImportResult:
    dry_run: bool
    rows: int
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    errors: list[dict] = field(default_factory=list)


def parse_trunk_csv(content: bytes, *, max_rows: int = 10_000, max_bytes: int = 5 * 1024 * 1024) -> ParsedTrunkCSV:
    if not isinstance(content, bytes) or len(content) > max_bytes:
        raise CSVSchemaError("csv_too_large")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CSVSchemaError("csv_encoding_invalid") from error
    reader = csv.DictReader(io.StringIO(text))
    required = {"technology", "device_user", "device_password"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise CSVSchemaError("csv_schema_invalid")
    rows: list[TrunkCSVRow] = []
    ignored = 0
    processed = 0
    for line, raw in enumerate(reader, start=2):
        processed += 1
        if processed > max_rows:
            raise CSVSchemaError("csv_row_limit")
        technology = (raw.get("technology") or "").strip().lower()
        if technology == "virtual":
            ignored += 1
            continue
        if technology not in {"sip", "pjsip"}:
            ignored += 1
            continue
        username = (raw.get("device_user") or "").strip()
        password = raw.get("device_password") or ""
        if not username or not password:
            raise CSVSchemaError("csv_row_invalid")
        rows.append(TrunkCSVRow(
            line=line,
            prefix=(raw.get("prefix") or raw.get("extension") or "").strip() or None,
            condominium_name=(raw.get("condominium") or raw.get("ext_name") or "").strip(),
            auth_username=username,
            password=password,
            sip_profile="internal-7060" if technology == "pjsip" else "internal",
            condominium_id=(raw.get("condominium_id") or "").strip() or None,
        ))
    return ParsedTrunkCSV(rows=rows, ignored=ignored)


async def import_trunk_csv(content, tenant_id, pbx_id, *, dry_run, trunk_service) -> TrunkImportResult:
    parsed = parse_trunk_csv(content)
    result = TrunkImportResult(dry_run=dry_run, rows=len(parsed.rows), unchanged=parsed.ignored)
    if dry_run:
        return result
    for row in parsed.rows:
        outcome = await trunk_service.upsert_imported(tenant_id=tenant_id, pbx_id=pbx_id, row=row)
        if outcome == "created":
            result.created += 1
        elif outcome == "updated":
            result.updated += 1
        else:
            result.unchanged += 1
    return result


def parse_trunk_json(
    content: bytes,
    *,
    condominium_name: str,
    max_bytes: int = 256 * 1024,
) -> TrunkCSVRow:
    if not isinstance(content, bytes) or len(content) > max_bytes:
        raise CSVSchemaError("trunk_json_too_large")
    try:
        document = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CSVSchemaError("trunk_json_invalid") from error
    if not isinstance(document, dict) or not condominium_name.strip():
        raise CSVSchemaError("trunk_json_schema_invalid")
    general = document.get("configuracoes_gerais")
    connection = document.get("general_configurations")
    if not isinstance(general, dict) or not isinstance(connection, dict):
        raise CSVSchemaError("trunk_json_schema_invalid")

    technology = str(general.get("tecnologia") or "").strip().lower()
    try:
        port = int(connection.get("porta"))
    except (TypeError, ValueError) as error:
        raise CSVSchemaError("trunk_json_sip_configuration_invalid") from error
    if technology != "pjsip" or port != 7060:
        raise CSVSchemaError("trunk_json_sip_configuration_invalid")

    remote_username = str(connection.get("nome_de_usuario_remoto") or "").strip()
    outgoing_username = str(connection.get("nome_de_usuario_de_saida") or "").strip()
    if not remote_username:
        raise CSVSchemaError("trunk_json_username_missing")
    if outgoing_username and outgoing_username != remote_username:
        raise CSVSchemaError("trunk_json_username_mismatch")

    remote_secret = connection.get("segredo_remoto")
    local_secret = connection.get("segredo_local")
    if not isinstance(remote_secret, str) or not remote_secret:
        raise CSVSchemaError("trunk_json_secret_missing")
    if local_secret not in (None, "", remote_secret):
        raise CSVSchemaError("trunk_json_credentials_mismatch")

    return TrunkCSVRow(
        line=1,
        prefix=None,
        condominium_name=condominium_name.strip(),
        auth_username=remote_username,
        password=remote_secret,
        sip_profile="internal-7060",
    )


async def import_trunk_json(
    content,
    tenant_id,
    pbx_id,
    *,
    condominium_name,
    condominium_id,
    dry_run,
    trunk_service,
) -> TrunkImportResult:
    row = parse_trunk_json(content, condominium_name=condominium_name)
    result = TrunkImportResult(dry_run=dry_run, rows=1)
    if dry_run:
        return result
    if not condominium_id:
        raise CSVSchemaError("trunk_json_condominium_missing")
    outcome = await trunk_service.upsert_imported(
        tenant_id=tenant_id,
        pbx_id=pbx_id,
        row=replace(row, condominium_id=condominium_id),
    )
    if outcome == "created":
        result.created = 1
    elif outcome == "updated":
        result.updated = 1
    else:
        result.unchanged = 1
    return result
