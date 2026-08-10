"""Cliente descartável que registra um ATA e captura evento Sofia sanitizado."""

import hashlib
import json
import os
import re
import socket
import time
import uuid

HOST = "zenith-freeswitch-spike-012"
USER = "spike012"
PASSWORD = "fixture-sip-password"
DOMAIN = "zenith.local"
EXPIRES = int(os.environ.get("SPIKE_EXPIRES_SECONDS", "120"))
TARGET_SUBCLASS = os.environ.get("SPIKE_TARGET_SUBCLASS", "sofia::register")
EVENT_TIMEOUT = int(os.environ.get("SPIKE_EVENT_TIMEOUT_SECONDS", "30"))


def receive_esl(sock):
    buffer = b""
    deadline = time.time() + EVENT_TIMEOUT
    while time.time() < deadline:
        try:
            buffer += sock.recv(65_536)
        except socket.timeout:
            continue
        header_end = buffer.find(b"\n\n")
        if header_end < 0:
            continue
        headers = buffer[:header_end].decode(errors="replace")
        match = re.search(r"Content-Length:\s*(\d+)", headers, re.I)
        size = int(match.group(1)) if match else 0
        start = header_end + 2
        if len(buffer) < start + size:
            continue
        body = buffer[start:start + size]
        buffer = buffer[start + size:]
        if not body:
            continue
        event = json.loads(body)
        if event.get("Event-Subclass") == TARGET_SUBCLASS:
            safe = {
                "event_name": event.get("Event-Name"),
                "event_subclass": event.get("Event-Subclass"),
                "available_keys": sorted(event),
                "profile_name": event.get("profile-name") or event.get("Profile-Name") or event.get("variable_sofia_profile_name"),
                "from_user": event.get("from-user") or event.get("from_user") or event.get("variable_sip_auth_username"),
            }
            print(json.dumps(safe, sort_keys=True))
            return
    raise RuntimeError("evento Sofia não recebido")


def register():
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.settimeout(5)
    call_id = f"{uuid.uuid4()}@spike"
    branch = f"z9hG4bK{uuid.uuid4().hex[:12]}"
    tag = uuid.uuid4().hex[:8]
    local = "172.30.0.99"

    def message(cseq, authorization=""):
        lines = [
            f"REGISTER sip:{DOMAIN} SIP/2.0",
            f"Via: SIP/2.0/UDP {local}:5068;branch={branch};rport",
            f"From: <sip:{USER}@{DOMAIN}>;tag={tag}",
            f"To: <sip:{USER}@{DOMAIN}>",
            f"Call-ID: {call_id}",
            f"CSeq: {cseq} REGISTER",
            f"Contact: <sip:{USER}@{local}:5068>",
            "Max-Forwards: 70",
            f"Expires: {EXPIRES}",
        ]
        if authorization:
            lines.append(authorization)
        lines.extend(["Content-Length: 0", "", ""])
        return "\r\n".join(lines).encode()

    udp.sendto(message(1), (HOST, 5060))
    challenge = udp.recv(65_536).decode(errors="replace")
    if " 401 " not in challenge:
        raise RuntimeError(f"challenge inesperado: {challenge.splitlines()[0]}")
    realm = re.search(r'realm="([^"]+)"', challenge).group(1)
    nonce = re.search(r'nonce="([^"]+)"', challenge).group(1)
    uri = f"sip:{DOMAIN}"
    ha1 = hashlib.md5(f"{USER}:{realm}:{PASSWORD}".encode()).hexdigest()
    ha2 = hashlib.md5(f"REGISTER:{uri}".encode()).hexdigest()
    digest = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
    authorization = (
        f'Authorization: Digest username="{USER}", realm="{realm}", nonce="{nonce}", '
        f'uri="{uri}", response="{digest}", algorithm=MD5'
    )
    udp.sendto(message(2, authorization), (HOST, 5060))
    accepted = udp.recv(65_536).decode(errors="replace")
    if " 200 " not in accepted:
        raise RuntimeError(f"registro rejeitado: {accepted.splitlines()[0]}")
    print(json.dumps({"register_status": 200, "username": USER}))


esl = socket.create_connection((HOST, 8021), timeout=5)
esl.settimeout(1)
esl.recv(4096)
esl.sendall(b"auth ClueCon\n\n")
if b"+OK" not in esl.recv(4096):
    raise RuntimeError("falha de autenticação ESL")
esl.sendall(b"events json CUSTOM sofia::register sofia::unregister sofia::expire SOFIA_REGISTER SOFIA_UNREGISTER\n\n")
esl.recv(4096)
register()
receive_esl(esl)
