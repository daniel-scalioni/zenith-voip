import json
import logging
import os
import socket
import time
from datetime import datetime, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("ip-watcher")


def get_external_ip(endpoint: str, mock_ip: str | None, verify_ssl: bool = True) -> str | None:
    if mock_ip:
        return mock_ip.strip()

    try:
        resp = requests.get(endpoint, timeout=5, verify=verify_ssl)
        resp.raise_for_status()
        return resp.text.strip()
    except requests.exceptions.RequestException as e:
        log.warning(json.dumps({"ts": _now(), "event": "http_fallback", "reason": str(e)}))

    # Fallback: source IP via getsockname() — works because sidecar uses network_mode: host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 53))
            ip = s.getsockname()[0]
            log.warning(json.dumps({"ts": _now(), "event": "getsockname_fallback", "ip": ip}))
            return ip
    except OSError as e:
        log.error(json.dumps({"ts": _now(), "event": "ip_discovery_failed", "reason": str(e)}))
        return None


def write_vars_xml(ip: str, conf_path: str) -> None:
    content = (
        "<include>\n"
        f'  <X-PRE-PROCESS cmd="set" data="external_sip_ip={ip}"/>\n'
        f'  <X-PRE-PROCESS cmd="set" data="external_rtp_ip={ip}"/>\n'
        "</include>\n"
    )
    path = os.path.join(conf_path, "vars-external-ip.xml")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.replace(tmp, path)


def _esl_send(host: str, port: int, password: str, commands: list[str]) -> list[str]:
    responses = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        s.connect((host, port))
        # consume auth request
        s.recv(4096)
        s.sendall(f"auth {password}\n\n".encode())
        s.recv(4096)
        for cmd in commands:
            s.sendall(f"api {cmd}\n\n".encode())
            time.sleep(0.2)
            data = b""
            s.settimeout(5)
            try:
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n\n" in data:
                        break
            except socket.timeout:
                pass
            responses.append(data.decode(errors="replace"))
    return responses


def get_current_ext_ip(host: str, port: int, password: str) -> str | None:
    try:
        responses = _esl_send(host, port, password, ["sofia status profile upstream"])
        output = responses[0] if responses else ""
        for line in output.splitlines():
            if "Ext-SIP-IP" in line:
                parts = line.split()
                if len(parts) >= 2:
                    return parts[-1].strip()
    except OSError:
        pass
    return None


def apply_update(host: str, port: int, password: str) -> bool:
    try:
        responses = _esl_send(host, port, password, ["reloadxml", "sofia profile upstream restart"])
        reload_ok = "+OK" in responses[0] if responses else False
        return reload_ok
    except OSError as e:
        log.error(json.dumps({"ts": _now(), "event": "esl_error", "detail": str(e)}))
        return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(ip_anterior: str | None, ip_atual: str | None, acao: str) -> None:
    log.info(json.dumps({
        "ts": _now(),
        "ip_anterior": ip_anterior,
        "ip_atual": ip_atual,
        "acao_tomada": acao,
    }))


def main() -> None:
    endpoint = os.environ.get("EXTERNAL_IP_ENDPOINT", "")
    mock_ip = os.environ.get("MOCK_EXTERNAL_IP", "").strip() or None
    esl_host = os.environ.get("FREESWITCH_ESL_HOST", "127.0.0.1")
    esl_port = int(os.environ.get("FREESWITCH_ESL_PORT", "8021"))
    esl_pass = os.environ.get("FREESWITCH_ESL_PASSWORD", "ClueCon")
    poll = int(os.environ.get("POLL_INTERVAL", "60"))
    verify_ssl = os.environ.get("SSL_VERIFY", "true").lower() in ("true", "1", "yes")
    conf_path = os.environ.get("FREESWITCH_CONF_PATH", "/etc/freeswitch")

    last_ip: str | None = None

    while True:
        try:
            current_ip = get_external_ip(endpoint, mock_ip, verify_ssl)

            if current_ip is None:
                log.error(json.dumps({"ts": _now(), "ip_anterior": last_ip, "ip_atual": None, "acao_tomada": "error"}))
                time.sleep(poll)
                continue

            freeswitch_ip = get_current_ext_ip(esl_host, esl_port, esl_pass)

            if last_ip is None:
                # startup: always apply to ensure correct IP from first cycle
                write_vars_xml(current_ip, conf_path)
                apply_update(esl_host, esl_port, esl_pass)
                _emit(None, current_ip, "startup")
                last_ip = current_ip
            elif current_ip != freeswitch_ip:
                write_vars_xml(current_ip, conf_path)
                apply_update(esl_host, esl_port, esl_pass)
                _emit(last_ip, current_ip, "update")
                last_ip = current_ip
            else:
                _emit(last_ip, current_ip, "none")

        except Exception as e:
            log.error(json.dumps({"ts": _now(), "ip_anterior": last_ip, "ip_atual": None, "acao_tomada": "error", "detail": str(e)}))

        time.sleep(poll)


if __name__ == "__main__":
    main()
