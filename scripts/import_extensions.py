#!/usr/bin/env python3
"""
Importa ramais do VitalPBX (GPhone) para o FreeSWITCH.

Lê o CSV exportado pelo VitalPBX e gera:
  - freeswitch/conf/directory/extensions.xml   (usuários para auth local)
  - freeswitch/conf/sip_profiles/upstream/     (gateways upstream por ramal)

Por padrão todos os gateways são gerados com register=false (seguro para produção).
Use --enable para ativar registros upstream somente nos ramais em migração.

Uso:
    # Gerar tudo com register=false (padrão seguro):
    python3 scripts/import_extensions.py specs/export_extensions.csv

    # Ativar somente o ramal 1001:
    python3 scripts/import_extensions.py specs/export_extensions.csv --enable 1001

    # Ativar múltiplos ramais:
    python3 scripts/import_extensions.py specs/export_extensions.csv --enable 1001,1002,1003

Após executar, copie os arquivos gerados para o servidor (não commitar — contêm senhas):
    scp freeswitch/conf/directory/extensions.xml  administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/directory/
    scp -r freeswitch/conf/sip_profiles/upstream/ administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/sip_profiles/

Para aplicar sem reiniciar o FreeSWITCH (só recarrega os gateways):
    docker exec freeswitch fs_cli -x "sofia profile upstream rescan"
"""

import argparse
import csv
import xml.sax.saxutils as saxutils
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DIRECTORY_OUT = REPO_ROOT / "freeswitch/conf/directory/extensions.xml"
UPSTREAM_DIR = REPO_ROOT / "freeswitch/conf/sip_profiles/upstream"

PBX_HOST = "sip.maisalerta.tecnorise.com"

# Porta de destino no VitalPBX por tecnologia SIP.
# PJSIP usa 7060; SIP usa 5060 (ou 5062 — verificar por perfil/ramal).
PORT_BY_TECH: dict[str, str] = {
    "pjsip": "7060",
    "sip": "5060",
}

COL_EXTENSION = "extension"
COL_EXT_NAME = "ext_name"
COL_TECHNOLOGY = "technology"
COL_DEVICE_USER = "device_user"
COL_DEVICE_PASSWORD = "device_password"


def escape(value: str) -> str:
    return saxutils.escape(value, {'"': "&quot;"})


def load_extensions(csv_path: Path) -> dict[str, dict]:
    """
    Lê o CSV e retorna dict {extension: {user, password, name, tech}}.
    Dedup: pjsip prevalece sobre sip (dispositivo provavelmente registrado via pjsip).
    Ignora: virtual, sem device_user, sem device_password.
    """
    extensions: dict[str, dict] = {}
    skipped_virtual = 0
    skipped_no_creds = 0
    duplicates_replaced = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        # Pula as 4 primeiras linhas descritivas do VitalPBX; linha 5 é o cabeçalho real
        for _ in range(4):
            next(f)
        reader = csv.DictReader(f)
        for row in reader:
            tech = row.get(COL_TECHNOLOGY, "").strip().strip('"')
            user = row.get(COL_DEVICE_USER, "").strip().strip('"')
            pwd = row.get(COL_DEVICE_PASSWORD, "").strip().strip('"')
            ext = row.get(COL_EXTENSION, "").strip().strip('"')
            name = row.get(COL_EXT_NAME, "").strip().strip('"')

            if tech == "virtual":
                skipped_virtual += 1
                continue
            if not user or not pwd or not ext:
                skipped_no_creds += 1
                continue

            entry = {"user": user, "password": pwd, "name": name, "tech": tech}

            if ext not in extensions:
                extensions[ext] = entry
            else:
                existing_tech = extensions[ext]["tech"]
                # pjsip prevalece sobre sip
                if tech == "pjsip" and existing_tech == "sip":
                    extensions[ext] = entry
                    duplicates_replaced += 1

    print(f"CSV processado:")
    print(f"  Extensões únicas importadas : {len(extensions)}")
    print(f"  Virtuais ignoradas           : {skipped_virtual}")
    print(f"  Sem credenciais ignoradas    : {skipped_no_creds}")
    print(f"  Duplicatas resolvidas (pjsip): {duplicates_replaced}")
    return extensions


def write_directory(extensions: dict[str, dict]) -> None:
    DIRECTORY_OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["<!-- Gerado por scripts/import_extensions.py — NÃO COMMITAR (contém senhas) -->"]
    for ext in sorted(extensions):
        e = extensions[ext]
        lines.append(f'<user id="{escape(ext)}">')
        lines.append(f'  <params>')
        lines.append(f'    <param name="password" value="{escape(e["password"])}"/>')
        lines.append(f'  </params>')
        lines.append(f'  <variables>')
        lines.append(f'    <variable name="user_context" value="default"/>')
        lines.append(f'    <variable name="toll_allow" value="local"/>')
        lines.append(f'    <variable name="effective_caller_id_name" value="{escape(e["name"])}"/>')
        lines.append(f'    <variable name="effective_caller_id_number" value="{escape(ext)}"/>')
        lines.append(f'  </variables>')
        lines.append(f'</user>')
    DIRECTORY_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nDirectory:  {DIRECTORY_OUT}  ({len(extensions)} usuários)")


def write_gateways(extensions: dict[str, dict], active: set[str]) -> None:
    UPSTREAM_DIR.mkdir(parents=True, exist_ok=True)
    # Remove arquivos anteriores para evitar gateways órfãos
    for f in UPSTREAM_DIR.glob("upstream-*.xml"):
        f.unlink()

    enabled_count = 0
    for ext in sorted(extensions):
        e = extensions[ext]
        gw_name = f"upstream-{ext}"
        register = "true" if ext in active else "false"
        if register == "true":
            enabled_count += 1
        port = PORT_BY_TECH.get(e["tech"], "5060")
        proxy = f"{PBX_HOST}:{port}"
        content = f"""<!-- Gerado por scripts/import_extensions.py — NÃO COMMITAR (contém senhas) -->
<gateway name="{escape(gw_name)}">
  <param name="username" value="{escape(e["user"])}"/>
  <param name="password" value="{escape(e["password"])}"/>
  <param name="proxy" value="{escape(proxy)}"/>
  <param name="register" value="{register}"/>
  <param name="caller-id-in-from" value="true"/>
  <param name="ping" value="25"/>
</gateway>
"""
        (UPSTREAM_DIR / f"{gw_name}.xml").write_text(content, encoding="utf-8")

    total = len(extensions)
    disabled = total - enabled_count
    print(f"Gateways:   {UPSTREAM_DIR}/  ({total} arquivos)")
    print(f"  register=true  (ativos) : {enabled_count}")
    print(f"  register=false (parados): {disabled}")
    if active - set(extensions.keys()):
        missing = active - set(extensions.keys())
        print(f"  AVISO: extensões em --enable não encontradas no CSV: {', '.join(sorted(missing))}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa ramais do VitalPBX para o FreeSWITCH."
    )
    parser.add_argument("csv_path", help="Caminho para o CSV exportado do VitalPBX")
    parser.add_argument(
        "--enable",
        default="",
        metavar="EXT1,EXT2,...",
        help="Ramais a ativar (register=true). Os demais ficam com register=false. "
             "Padrão: nenhum (todos desabilitados, seguro para produção).",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"Erro: arquivo não encontrado: {csv_path}")
        raise SystemExit(1)

    active = {e.strip() for e in args.enable.split(",") if e.strip()}

    extensions = load_extensions(csv_path)
    if not extensions:
        print("Nenhuma extensão válida encontrada. Verifique o CSV.")
        raise SystemExit(1)

    write_directory(extensions)
    write_gateways(extensions, active)

    active_str = f"--enable {args.enable}" if active else ""
    print(f"""
Próximos passos:
  1. Copie os arquivos gerados para o servidor (NÃO commitar):
       scp freeswitch/conf/directory/extensions.xml administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/directory/
       scp -r freeswitch/conf/sip_profiles/upstream/ administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/sip_profiles/

  2. Recarregue os gateways sem reiniciar o FreeSWITCH:
       docker exec freeswitch fs_cli -x "sofia profile upstream rescan"

  3. Verifique o gateway ativo:
       docker exec freeswitch fs_cli -x "sofia status gateway upstream-1001"

  Para ativar mais ramais depois:
       python3 scripts/import_extensions.py {args.csv_path} --enable 1001,1002
       (repetir os passos 1 e 2)
""")


if __name__ == "__main__":
    main()
