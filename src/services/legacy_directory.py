"""Provider somente leitura para os usuários XML legados do FreeSWITCH."""

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


class LegacyDirectoryError(ValueError):
    pass


@dataclass(frozen=True, repr=False)
class LegacyDirectoryUser:
    username: str
    password: str
    params: tuple[tuple[str, str], ...]
    variables: tuple[tuple[str, str], ...]


class LegacyDirectoryProvider:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._mtime_ns: int | None = None
        self._users: dict[str, LegacyDirectoryUser] = {}

    def __repr__(self) -> str:
        return f"LegacyDirectoryProvider(path={self._path!s}, users={len(self._users)})"

    def _refresh(self) -> None:
        try:
            stat = self._path.stat()
        except FileNotFoundError:
            self._mtime_ns = None
            self._users = {}
            return
        if self._mtime_ns == stat.st_mtime_ns:
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            lowered = raw.lower()
            if "<!doctype" in lowered or "<!entity" in lowered:
                raise LegacyDirectoryError("legacy_directory_unsafe_xml")
            try:
                root = ET.fromstring(raw)
            except ET.ParseError:
                root = ET.fromstring(f"<legacy-directory>{raw}</legacy-directory>")
        except LegacyDirectoryError:
            raise
        except (OSError, ET.ParseError, UnicodeError) as error:
            raise LegacyDirectoryError("legacy_directory_invalid") from error

        users: dict[str, LegacyDirectoryUser] = {}
        candidates = [root] if root.tag == "user" else list(root.findall(".//user"))
        for element in candidates:
            username = element.attrib.get("id", "").strip()
            if not username or username in users:
                raise LegacyDirectoryError("legacy_directory_ambiguous_user")
            params = tuple(
                (item.attrib.get("name", ""), item.attrib.get("value", ""))
                for item in element.findall("./params/param")
            )
            variables = tuple(
                (item.attrib.get("name", ""), item.attrib.get("value", ""))
                for item in element.findall("./variables/variable")
            )
            password = next((value for name, value in params if name == "password"), "")
            users[username] = LegacyDirectoryUser(username, password, params, variables)
        self._users = users
        self._mtime_ns = stat.st_mtime_ns

    def lookup(self, username: str) -> LegacyDirectoryUser | None:
        self._refresh()
        return self._users.get(username)

    def contains(self, profile: str, username: str) -> bool:
        if profile not in {"internal", "internal-7060", "internal-5062"}:
            return False
        return self.lookup(username) is not None
