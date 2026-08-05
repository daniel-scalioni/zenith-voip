#!/usr/bin/env python3
"""Renderiza o binding XML Curl privado sem escrever segredo em stdout."""

import argparse
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"configuração obrigatória ausente: {name}")
    return value


def render() -> str:
    username = _required("FREESWITCH_DIRECTORY_BASIC_USERNAME")
    password = _required("FREESWITCH_DIRECTORY_BASIC_PASSWORD")
    url = _required("FREESWITCH_DIRECTORY_URL")
    timeout = os.environ.get("FREESWITCH_DIRECTORY_TIMEOUT_SECONDS", "2").strip()
    try:
        if not 0 < float(timeout) <= 10:
            raise ValueError
    except ValueError as error:
        raise SystemExit("timeout XML Curl inválido") from error

    configuration = ET.Element("configuration", {
        "name": "xml_curl.conf", "description": "Zenith internal directory",
    })
    bindings = ET.SubElement(configuration, "bindings")
    binding = ET.SubElement(bindings, "binding", {"name": "zenith-directory"})
    ET.SubElement(binding, "param", {
        "name": "gateway-url", "value": url, "bindings": "directory",
    })
    ET.SubElement(binding, "param", {"name": "gateway-credentials", "value": f"{username}:{password}"})
    ET.SubElement(binding, "param", {"name": "auth-scheme", "value": "basic"})
    ET.SubElement(binding, "param", {"name": "method", "value": "POST"})
    ET.SubElement(binding, "param", {"name": "timeout", "value": timeout})
    ET.SubElement(binding, "param", {"name": "disable-100-continue", "value": "true"})
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(configuration, encoding="unicode") + "\n"


def write_atomic(output: Path, payload: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
        output.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_atomic(args.output, render())


if __name__ == "__main__":
    main()
