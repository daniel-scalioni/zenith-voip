"""Servidor descartável do spike T042; registra apenas chaves e campos seguros."""

import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import parse_qs
import xml.etree.ElementTree as ET

USERNAME = "fixture-user"
PASSWORD = "fixture-password"
SIP_PASSWORD = "fixture-sip-password"


def response_xml(username: str) -> bytes:
    document = ET.Element("document", {"type": "freeswitch/xml"})
    section = ET.SubElement(document, "section", {"name": "directory"})
    domain = ET.SubElement(section, "domain", {"name": "zenith.local"})
    users = ET.SubElement(ET.SubElement(ET.SubElement(domain, "groups"), "group", {"name": "default"}), "users")
    user = ET.SubElement(users, "user", {"id": username})
    params = ET.SubElement(user, "params")
    ET.SubElement(params, "param", {"name": "password", "value": SIP_PASSWORD})
    variables = ET.SubElement(user, "variables")
    ET.SubElement(variables, "variable", {"name": "user_context", "value": "default"})
    ET.SubElement(variables, "variable", {"name": "zenith_trunk_id", "value": "00000000-0000-0000-0000-000000000012"})
    return ET.tostring(document, encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _respond(self, fields):
        safe = {
            "method": self.command,
            "keys": sorted(fields),
            "section": fields.get("section"),
            "tag_name": fields.get("tag_name"),
            "key_name": fields.get("key_name"),
            "key_value": fields.get("key_value"),
            "user": fields.get("user"),
            "sip_profile_name": fields.get("sip_profile_name"),
            "variable_sofia_profile_name": fields.get("variable_sofia_profile_name"),
        }
        print(json.dumps(safe, sort_keys=True), flush=True)
        username = fields.get("user") or fields.get("sip_auth_username") or fields.get("key_value") or "spike012"
        payload = response_xml(username)
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self):
        expected = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
        if self.headers.get("Authorization") != expected:
            print(json.dumps({"method": self.command, "unauthorized": True}), flush=True)
            self.send_response(401)
            self.end_headers()
            return False
        return True

    def do_POST(self):
        if not self._authorized():
            return
        length = min(int(self.headers.get("Content-Length", "0")), 65_536)
        fields = {key: values[-1] for key, values in parse_qs(self.rfile.read(length).decode(errors="replace")).items()}
        self._respond(fields)

    def do_GET(self):
        if not self._authorized():
            return
        query = self.path.partition("?")[2]
        fields = {key: values[-1] for key, values in parse_qs(query).items()}
        self._respond(fields)


HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
