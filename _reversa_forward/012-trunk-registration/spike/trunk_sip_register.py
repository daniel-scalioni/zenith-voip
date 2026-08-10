"""Prova o registro SIP de um tronco ATA contra o FreeSWITCH, com saída sanitizada.

Lê o veículo de exportação por stdin, mantém a credencial apenas em memória e
imprime somente códigos de status e o hash da identidade — nunca usuário ou senha.

Sequência provada, na ordem exigida pelo gate T044:
  1. REGISTER com senha incorreta  -> deve ser recusado (401/403)
  2. REGISTER com senha correta     -> deve ser aceito (200)
  3. REGISTER com Expires: 0        -> remove o contato (200)

Uso:
    python trunk_sip_register.py --host 10.10.10.11 --port 7060 --numero 1780
    < export_extension_trunks.json
"""

import argparse
import hashlib
import json
import socket
import sys
import uuid

from legacy_sip_register import _status, build_digest_authorization


def _credential(document: dict, numero: str) -> tuple[str, str]:
    for item in document.get("ramais", []):
        if str(item.get("numero")) != numero:
            continue
        connection = item.get("configuracoes", {}).get("autenticacao_e_rede", {})
        username = str(connection.get("nome_de_usuario_remoto") or "").strip()
        secret = str(connection.get("segredo_remoto") or "")
        if not username or not secret:
            raise RuntimeError("trunk_credential_incomplete")
        return username, secret
    raise RuntimeError("trunk_not_found_in_document")


def _attempt(host: str, port: int, username: str, password: str, expires: int, timeout: float) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    local_host, local_port = sock.getsockname()
    call_id = f"{uuid.uuid4()}@zenith-trunk-gate"
    tag = uuid.uuid4().hex[:12]
    cnonce = uuid.uuid4().hex
    request_uri = f"sip:{host}"

    def message(cseq: int, authorization: str = "") -> bytes:
        branch = f"z9hG4bK{uuid.uuid4().hex}"
        lines = [
            f"REGISTER {request_uri} SIP/2.0",
            f"Via: SIP/2.0/UDP {local_host}:{local_port};branch={branch};rport",
            "Max-Forwards: 70",
            f"From: <sip:{username}@{host}>;tag={tag}",
            f"To: <sip:{username}@{host}>",
            f"Call-ID: {call_id}",
            f"CSeq: {cseq} REGISTER",
            f"Contact: <sip:{username}@{local_host}:{local_port}>",
            f"Expires: {expires}",
            "User-Agent: zenith-trunk-gate",
            "Content-Length: 0",
        ]
        if authorization:
            lines.insert(-1, f"Authorization: {authorization}")
        return ("\r\n".join(lines) + "\r\n\r\n").encode()

    try:
        sock.send(message(1))
        challenge = sock.recv(65535).decode(errors="replace")
        status = _status(challenge)
        if status != 401:
            return status
        authorization = build_digest_authorization(
            challenge=challenge, username=username, password=password, method="REGISTER",
            uri=request_uri, nonce_count=1, cnonce=cnonce,
        )
        sock.send(message(2, authorization))
        return _status(sock.recv(65535).decode(errors="replace"))
    finally:
        sock.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=7060)
    parser.add_argument("--numero", required=True)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    document = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    username, password = _credential(document, args.numero)
    identity_hash = hashlib.sha256(username.encode()).hexdigest()

    wrong = _attempt(args.host, args.port, username, password + "-invalido", 120, args.timeout)
    right = _attempt(args.host, args.port, username, password, 120, args.timeout)
    removal = _attempt(args.host, args.port, username, password, 0, args.timeout)

    print(json.dumps({
        "identity_sha256": identity_hash,
        "register_wrong_password_status": wrong,
        "register_correct_password_status": right,
        "unregister_status": removal,
    }, indent=2))
    return 0 if (wrong in (401, 403) and right == 200 and removal == 200) else 1


if __name__ == "__main__":
    raise SystemExit(main())
