"""Compara o diretório legado com a resposta do backend sem expor identidades."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from src.api.freeswitch_directory import build_directory_xml
from src.services.legacy_directory import LegacyDirectoryProvider


def _items(element: ET.Element, path: str, tag: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (item.attrib.get("name", ""), item.attrib.get("value", ""))
        for item in element.findall(f"{path}/{tag}")
    )


def compare(path: Path) -> dict[str, int | str]:
    raw = path.read_text(encoding="utf-8")
    lowered = raw.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise ValueError("unsafe_legacy_directory")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        root = ET.fromstring(f"<legacy-directory>{raw}</legacy-directory>")
    source_users = [root] if root.tag == "user" else list(root.findall(".//user"))
    provider = LegacyDirectoryProvider(path)
    identities: list[str] = []
    missing = 0
    mismatches = 0
    oversized = 0

    for source in source_users:
        username = source.attrib.get("id", "").strip()
        identities.append(username)
        legacy = provider.lookup(username)
        if legacy is None:
            missing += 1
            continue
        payload = build_directory_xml(
            "comparison.invalid",
            {
                "auth_username": legacy.username,
                "password": legacy.password,
                "params": legacy.params,
                "variables": legacy.variables,
            },
        )
        oversized += len(payload.encode("utf-8")) > 65_536
        rendered = ET.fromstring(payload).find(".//user")
        if rendered is None:
            mismatches += 1
            continue
        equivalent = (
            rendered.attrib.get("id") == username
            and _items(rendered, "./params", "param") == legacy.params
            and _items(rendered, "./variables", "variable") == legacy.variables
        )
        mismatches += not equivalent

    identity_digest = hashlib.sha256("\n".join(sorted(identities)).encode()).hexdigest()
    return {
        "source_users": len(source_users),
        "unique_users": len(set(identities)),
        "missing": missing,
        "mismatches": mismatches,
        "oversized": oversized,
        "identity_set_sha256": identity_digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(args.path), sort_keys=True))


if __name__ == "__main__":
    main()
