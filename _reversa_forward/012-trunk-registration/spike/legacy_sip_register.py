"""Prova um registro SIP legado e remove o contato sem expor credenciais."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import uuid

from src.services.legacy_directory import LegacyDirectoryProvider


def _digest(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


def _challenge_values(challenge: str) -> dict[str, str]:
    return {
        key.lower(): value
        for key, quoted, plain in re.findall(r'(\w+)=(?:"([^"]*)"|([^,\s]+))', challenge)
        if (value := quoted or plain)
    }


def build_digest_authorization(
    *,
    challenge: str,
    username: str,
    password: str,
    method: str,
    uri: str,
    nonce_count: int,
    cnonce: str,
) -> str:
    values = _challenge_values(challenge)
    realm = values.get("realm", "")
    nonce = values.get("nonce", "")
    if not realm or not nonce:
        raise RuntimeError("sip_challenge_invalid")
    ha1 = _digest(f"{username}:{realm}:{password}")
    ha2 = _digest(f"{method}:{uri}")
    offered_qop = {
        item.strip().lower() for item in values.get("qop", "").split(",") if item.strip()
    }
    if offered_qop and "auth" not in offered_qop:
        raise RuntimeError("sip_qop_unsupported")
    qop = "auth" if "auth" in offered_qop else ""
    parts = [
        f'username="{username}"',
        f'realm="{realm}"',
        f'nonce="{nonce}"',
        f'uri="{uri}"',
    ]
    if qop:
        nc = f"{nonce_count:08x}"
        response = _digest(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
        parts.extend([f"response=\"{response}\"", f"qop={qop}", f"nc={nc}", f'cnonce="{cnonce}"'])
    else:
        response = _digest(f"{ha1}:{nonce}:{ha2}")
        parts.append(f'response="{response}"')
    opaque = values.get("opaque")
    if opaque:
        parts.append(f'opaque="{opaque}"')
    parts.append("algorithm=MD5")
    return "Digest " + ", ".join(parts)


def sanitized_result(username: str, register_status: int, unregister_status: int) -> dict[str, int | str]:
    return {
        "register_status": register_status,
        "unregister_status": unregister_status,
        "identity_sha256": hashlib.sha256(username.encode()).hexdigest(),
    }


def _status(response: str) -> int:
    match = re.match(r"SIP/2.0\s+(\d{3})", response)
    if match is None:
        raise RuntimeError("sip_response_invalid")
    return int(match.group(1))


def _receive_final(sock: socket.socket) -> str:
    while True:
        response = sock.recv(65_536).decode(errors="replace")
        if _status(response) >= 200:
            return response


def register(path: Path, host: str, port: int, timeout: float) -> dict[str, int | str]:
    provider = LegacyDirectoryProvider(path)
    raw = path.read_text(encoding="utf-8")
    identities = re.findall(r'<user\s+[^>]*id="([^"]+)"', raw)
    legacy = next((provider.lookup(identity) for identity in identities if provider.lookup(identity)), None)
    if legacy is None or not legacy.password:
        raise RuntimeError("legacy_identity_unavailable")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    local_host, local_port = sock.getsockname()
    request_uri = f"sip:{host}"
    call_id = f"{uuid.uuid4()}@zenith-spike"
    tag = uuid.uuid4().hex[:12]
    cnonce = uuid.uuid4().hex

    def message(cseq: int, expires: int, authorization: str = "") -> bytes:
        branch = f"z9hG4bK{uuid.uuid4().hex}"
        lines = [
            f"REGISTER {request_uri} SIP/2.0",
            f"Via: SIP/2.0/UDP {local_host}:{local_port};branch={branch};rport",
            f"From: <sip:{legacy.username}@{host}>;tag={tag}",
            f"To: <sip:{legacy.username}@{host}>",
            f"Call-ID: {call_id}",
            f"CSeq: {cseq} REGISTER",
            f"Contact: <sip:{legacy.username}@{local_host}:{local_port}>",
            "Max-Forwards: 70",
            f"Expires: {expires}",
        ]
        if authorization:
            lines.append(f"Authorization: {authorization}")
        lines.extend(["Content-Length: 0", "", ""])
        return "\r\n".join(lines).encode()

    try:
        sock.send(message(1, 30))
        challenge_response = _receive_final(sock)
        if _status(challenge_response) != 401:
            raise RuntimeError("sip_challenge_rejected")
        challenge_match = re.search(r"WWW-Authenticate:\s*(Digest .+)", challenge_response, re.I)
        if challenge_match is None:
            raise RuntimeError("sip_challenge_invalid")
        challenge = challenge_match.group(1).strip()
        authorization = build_digest_authorization(
            challenge=challenge,
            username=legacy.username,
            password=legacy.password,
            method="REGISTER",
            uri=request_uri,
            nonce_count=1,
            cnonce=cnonce,
        )
        sock.send(message(2, 30, authorization))
        register_status = _status(_receive_final(sock))
        if register_status != 200:
            raise RuntimeError(f"sip_register_failed_{register_status}")

        authorization = build_digest_authorization(
            challenge=challenge,
            username=legacy.username,
            password=legacy.password,
            method="REGISTER",
            uri=request_uri,
            nonce_count=2,
            cnonce=cnonce,
        )
        sock.send(message(3, 0, authorization))
        unregister_status = _status(_receive_final(sock))
        return sanitized_result(legacy.username, register_status, unregister_status)
    finally:
        sock.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=7060)
    parser.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args()
    print(json.dumps(register(args.path, args.host, args.port, args.timeout), sort_keys=True))


if __name__ == "__main__":
    main()
