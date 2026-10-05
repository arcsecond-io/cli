"""The network manifest: every connection an installation makes or accepts.

`manifest.toml`, beside this file, is the source. This module reads it,
refuses a manifest that is not well formed, and answers the one question the
continuous-integration guard and `arcsecond doctor` both ask: is this
destination declared?

TOML rather than YAML because Python reads it without a dependency, and this
tool is installed on observatory machines.
"""

import tomllib
from dataclasses import dataclass, field
from importlib import resources
from typing import List, Optional, Tuple

FROM = ("stack", "browser", "tool", "docker")
DIRECTIONS = ("outbound", "local-network")
TRANSPORTS = ("tcp", "udp")
NEEDS = ("required", "recommended", "optional")
PROXY = ("yes", "no", "untested")
TESTS = ("handshake", "connect", "none")
EVIDENCE = ("captured", "code")

_TEXT_FIELDS = ("purpose", "feature", "frequency", "without_it", "enabled_by")


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Destination:
    id: str
    origin: str  # `from` in the file; a reserved word here
    direction: str
    names: Tuple[str, ...]
    port: int
    transport: str
    encrypted: bool
    need: str
    enabled_by: str
    purpose: str
    feature: str
    frequency: str
    data_sent: Tuple[str, ...]
    without_it: str
    proxy: str
    test: str
    evidence: str

    @property
    def always_on(self) -> bool:
        return self.enabled_by.startswith("always")

    def covers(self, name: str, port: int) -> bool:
        """Whether a connection to ``name`` on ``port`` is this entry. A name
        covers its sub-domains: map and sky tiles are served from numbered or
        lettered hosts under the one that is declared."""
        if port != self.port:
            return False
        name = name.rstrip(".").lower()
        return any(name == n or name.endswith("." + n) for n in self.names)


@dataclass(frozen=True)
class Listening:
    id: str
    port: int
    bound_to: str
    encrypted: bool
    purpose: str
    reached_by: str
    optional: bool = False


@dataclass(frozen=True)
class Manifest:
    version: int
    audited: str
    never_sent: Tuple[str, ...]
    destinations: Tuple[Destination, ...] = field(default_factory=tuple)
    listening: Tuple[Listening, ...] = field(default_factory=tuple)

    def find(self, name: str, port: int, origin: Optional[str] = None) -> Optional[Destination]:
        for d in self.destinations:
            if origin is not None and d.origin != origin:
                continue
            if d.covers(name, port):
                return d
        return None

    def of(self, origin: str) -> List[Destination]:
        return [d for d in self.destinations if d.origin == origin]


def _require(entry: dict, key: str, kind, where: str):
    if key not in entry:
        raise ManifestError(f"{where}: missing `{key}`")
    value = entry[key]
    # bool is an int in Python; a port must not be `true`.
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ManifestError(f"{where}: `{key}` must be {kind.__name__}")
    return value


def _one_of(entry: dict, key: str, allowed, where: str) -> str:
    value = _require(entry, key, str, where)
    if value not in allowed:
        raise ManifestError(f"{where}: `{key}` is {value!r}, not one of {', '.join(allowed)}")
    return value


def _destination(entry: dict, index: int) -> Destination:
    where = f"destination {entry.get('id', '#%d' % index)}"
    names = tuple(n.lower() for n in _require(entry, "names", list, where))
    port = _require(entry, "port", int, where)
    direction = _one_of(entry, "direction", DIRECTIONS, where)
    for key in _TEXT_FIELDS:
        if not _require(entry, key, str, where).strip():
            raise ManifestError(f"{where}: `{key}` is empty")
    if direction == "outbound" and not names and entry.get("test") != "none":
        raise ManifestError(f"{where}: an outbound entry with no name cannot be tested")
    if names and not 0 < port < 65536:
        raise ManifestError(f"{where}: port {port} is not a port")
    return Destination(
        id=_require(entry, "id", str, where),
        origin=_one_of(entry, "from", FROM, where),
        direction=direction,
        names=names,
        port=port,
        transport=_one_of(entry, "transport", TRANSPORTS, where),
        encrypted=_require(entry, "encrypted", bool, where),
        need=_one_of(entry, "need", NEEDS, where),
        enabled_by=entry["enabled_by"],
        purpose=entry["purpose"],
        feature=entry["feature"],
        frequency=entry["frequency"],
        data_sent=tuple(_require(entry, "data_sent", list, where)),
        without_it=entry["without_it"],
        proxy=_one_of(entry, "proxy", PROXY, where),
        test=_one_of(entry, "test", TESTS, where),
        evidence=_one_of(entry, "evidence", EVIDENCE, where),
    )


def _listening(entry: dict, index: int) -> Listening:
    where = f"listening {entry.get('id', '#%d' % index)}"
    return Listening(
        id=_require(entry, "id", str, where),
        port=_require(entry, "port", int, where),
        bound_to=_one_of(entry, "bound_to", ("every interface", "this machine only"), where),
        encrypted=_require(entry, "encrypted", bool, where),
        purpose=_require(entry, "purpose", str, where),
        reached_by=_require(entry, "reached_by", str, where),
        optional=bool(entry.get("optional", False)),
    )


def parse(text: str) -> Manifest:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ManifestError(f"not valid TOML: {e}") from None
    destinations = tuple(_destination(e, i) for i, e in enumerate(data.get("destination", [])))
    listening = tuple(_listening(e, i) for i, e in enumerate(data.get("listening", [])))
    for kind, entries in (("destination", destinations), ("listening", listening)):
        ids = [e.id for e in entries]
        twice = sorted({i for i in ids if ids.count(i) > 1})
        if twice:
            raise ManifestError(f"{kind} id used twice: {', '.join(twice)}")
    return Manifest(
        version=_require(data, "version", int, "manifest"),
        audited=_require(data, "audited", str, "manifest"),
        never_sent=tuple(_require(data, "never_sent", list, "manifest")),
        destinations=destinations,
        listening=listening,
    )


def packaged_text() -> str:
    return resources.files(__name__).joinpath("manifest.toml").read_text(encoding="utf-8")


def load() -> Manifest:
    """The manifest this version of the tool ships with."""
    return parse(packaged_text())
