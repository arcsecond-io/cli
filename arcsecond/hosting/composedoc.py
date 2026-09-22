"""The services and the environment of an installation, described from the
files that define them.

The packaged docker-compose.yml is written by this tool, and its comments are
deliberately operator documentation — they say why a port is not published,
what a bind mount is for, which service is optional. Paraphrasing them into a
page would give the page a life of its own and let it drift; instead the page
is produced from the template, so what an installation runs and what the
documentation says it runs are the same text.

The same goes for .env: the keys `arcsecond setup` writes are listed from the
provider table it writes them from, and the ones only the backend reads are
listed here, next to it, with a test that keeps the two in step.

No YAML library: the template is regular (services at two spaces, their keys
at four) and a small reader that keeps the comments is the whole point — a
YAML parser would drop them. Any change to the template's shape that this
reader cannot follow fails the tests that run it against the packaged file.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .local import (
    FRONTEND_HOST_ENV_KEY,
    OPTIONAL_SERVICES,
    OPTIONAL_SERVICES_ENV_KEY,
    REQUIRED_ENV_PROVIDERS,
    _compose_version,
    packaged_compose_text,
)

MARKER_START = re.compile(r"^\s*# >>> arcsecond:(\S+)\s*$")
MARKER_END = re.compile(r"^\s*# <<< arcsecond:(\S+)\s*$")
ENV_REF = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-[^}]*)?\}")


@dataclass
class Service:
    name: str
    description: List[str] = field(default_factory=list)  # the comment block above it
    notes: List[str] = field(default_factory=list)  # comments inside it
    image: Optional[str] = None
    container_name: Optional[str] = None
    restart: Optional[str] = None
    entrypoint: Optional[str] = None
    ports: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    volumes: List[str] = field(default_factory=list)
    healthcheck: bool = False
    stop_grace_period: Optional[str] = None
    env_vars: List[str] = field(default_factory=list)
    optional: Optional[str] = None  # the marker name, e.g. "alerts"


def _strip_comment(line: str) -> str:
    return line.strip().lstrip("#").strip()


class _Reader:
    """Walks the template line by line, keeping the comments."""

    def __init__(self):
        self.services: List[Service] = []
        self.current: Optional[Service] = None
        self.pending: List[str] = []  # comments waiting for the next service
        self.optional: Optional[str] = None
        self.in_services = False
        self.section: Optional[str] = None  # the 4-space key whose list we are in

    def feed(self, raw: str) -> None:
        if not raw.strip():
            self.pending = []
            return
        if self._marker(raw):
            return
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if indent == 0:
            self.in_services = stripped == "services:"
            self.current = None
            self.pending = []
        elif not self.in_services:
            return
        elif indent == 2:
            self._service_line(stripped)
        elif self.current is not None:
            self._body_line(indent, stripped)

    def _marker(self, raw: str) -> bool:
        start = MARKER_START.match(raw)
        if start:
            self.optional = start.group(1)
            return True
        if MARKER_END.match(raw):
            self.optional = None
            self.current = None
            return True
        return False

    def _service_line(self, stripped: str) -> None:
        if stripped.startswith("#"):
            self.pending.append(_strip_comment(stripped))
        elif stripped.endswith(":"):
            self.current = Service(
                name=stripped[:-1], description=self.pending, optional=self.optional
            )
            self.services.append(self.current)
            self.pending = []
            self.section = None

    def _body_line(self, indent: int, stripped: str) -> None:
        current = self.current
        for var in ENV_REF.findall(stripped):
            if var not in current.env_vars:
                current.env_vars.append(var)
        if stripped.startswith("#"):
            current.notes.append(_strip_comment(stripped))
        elif indent == 4:
            self._key(stripped)
        elif indent >= 6:
            self._list_item(indent, stripped)

    def _key(self, stripped: str) -> None:
        key, _, value = stripped.partition(":")
        value = value.strip()
        self.section = key
        scalar = {
            "image": "image",
            "container_name": "container_name",
            "restart": "restart",
            "entrypoint": "entrypoint",
            "stop_grace_period": "stop_grace_period",
        }
        if key in scalar:
            setattr(self.current, scalar[key], value)
        elif key == "healthcheck":
            self.current.healthcheck = True
        elif key == "ports" and value.startswith("["):
            self.current.ports += [
                p.strip().strip('"') for p in value.strip("[]").split(",") if p.strip()
            ]

    def _list_item(self, indent: int, stripped: str) -> None:
        current, section = self.current, self.section
        if section == "ports" and stripped.startswith("- "):
            current.ports.append(stripped[2:].strip().strip('"'))
        elif section == "depends_on":
            if stripped.startswith("- "):
                current.depends_on.append(stripped[2:].strip())
            elif indent == 6 and stripped.endswith(":"):
                current.depends_on.append(stripped[:-1])
        elif section == "volumes":
            self._volume(indent, stripped)

    def _volume(self, indent: int, stripped: str) -> None:
        volumes = self.current.volumes
        if (
            indent == 6
            and stripped.startswith("- ")
            and not stripped.startswith("- type")
        ):
            volumes.append(stripped[2:].strip())
        elif stripped.startswith("source:"):
            volumes.append(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("target:") and volumes:
            volumes[-1] += f" → {stripped.split(':', 1)[1].strip()}"


def parse_services(text: str) -> List[Service]:
    """The services of a compose template, comments kept."""
    reader = _Reader()
    for raw in text.splitlines():
        reader.feed(raw)
    return reader.services


# ---------------------------------------------------------------------------
# .env
# ---------------------------------------------------------------------------

SETUP = "written by `arcsecond setup`"
OPERATOR = "set by the operator"
BACKEND = "read by the backend"

# key -> (who sets it, what it is for). Every key `setup` writes must appear;
# the test enforces it. Keys only the backend reads are listed too, since an
# operator editing .env has no other place to learn they exist.
ENV_KEYS: Dict[str, tuple] = {
    "SECRET_KEY": (
        SETUP,
        "Django's secret key: signs sessions and tokens. Generated once; changing it logs everyone out.",
    ),
    "AUTH_JWT_SIGNING_KEY": (
        SETUP,
        "Signs the access tokens of the web interface and the CLI. Changing it logs everyone out.",
    ),
    "AGENT_JWT_SIGNING_KEY": (
        SETUP,
        "Signs the tokens of the equipment agents talking to the Control Room.",
    ),
    "FIELD_ENCRYPTION_KEY": (
        SETUP,
        "Encrypts sensitive fields in the database — external-storage credentials among them. "
        "Losing it makes those fields unreadable.",
    ),
    "SHARED_DATA_PATH": (
        SETUP,
        "The folder on this machine where the installation keeps everything it persists: data files, previews, "
        "caches, database backups. Mounted as /data inside the containers. Asked at setup.",
    ),
    "POSTGRES_USER": (SETUP, "The database role. Stable across installs."),
    "POSTGRES_PASSWORD": (
        SETUP,
        "The role's password, generated per install. Only read by Postgres on the very first boot; rotate it with "
        "`arcsecond db set-password`, never by editing this line alone.",
    ),
    "POSTGRES_DB": (SETUP, "The database name."),
    "GCN_CONSUMER_CLIENT_ID": (
        OPERATOR,
        "NASA GCN client credentials for the optional transient-alerts service. Empty until you paste yours.",
    ),
    "GCN_CONSUMER_CLIENT_SECRET": (OPERATOR, "See GCN_CONSUMER_CLIENT_ID."),
    FRONTEND_HOST_ENV_KEY: (
        OPERATOR,
        "The address other computers reach the installation at, port included (e.g. 192.168.1.42:5555). The backend "
        "builds invitation and password-reset links from it. Empty means localhost:5555. "
        "Set with `arcsecond setup --lan-host`.",
    ),
    OPTIONAL_SERVICES_ENV_KEY: (
        SETUP,
        "The operator's yes/no answers about optional services (e.g. `alerts:yes`), so setup does not ask again.",
    ),
    "HOSTED_FRONTEND_SCHEME": (
        BACKEND,
        "`http` (default) or `https`, when a TLS-terminating reverse proxy of your own sits in front of the installation.",
    ),
    "HOSTED_EXTRA_TRUSTED_ORIGINS": (
        BACKEND,
        "Comma-separated origins, scheme included, to trust besides private-network addresses — a public domain, "
        "a Tailscale name. Not needed for a LAN address.",
    ),
    "LIVE_IMAGE_PROXY_URL": (
        BACKEND,
        "Where the backend reaches the live-image proxy for cameras. Default http://host.docker.internal:8765; "
        "change it only for a proxy on another machine, then `arcsecond restart backend`.",
    ),
    "LOCAL_EMAIL_VERIFICATION_GRACE_HOURS": (
        BACKEND,
        "How long a new member may use the installation before verifying their email, "
        "on an installation with no mail server.",
    ),
}


def env_keys_written_by_setup() -> List[str]:
    return list(REQUIRED_ENV_PROVIDERS)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _frontmatter(title: str, cli_version: str, template_version: Optional[str]) -> str:
    return (
        "---\n"
        f'title: "{title}"\n'
        "visibility: public\n"
        "audience: operator\n"
        "tier: reference\n"
        "source: generated\n"
        f'cli: "{cli_version}"\n'
        f'template: "{template_version or "?"}"\n'
        "---\n\n\n"
    )


def _esc(text: str) -> str:
    return (
        text.replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("{{", "&#123;&#123;")
        .replace("|", "\\|")
    )


def _service_row(s: Service) -> str:
    ports = ", ".join(f"`{p}`" for p in s.ports) or "none"
    deps = ", ".join(f"`{d}`" for d in s.depends_on) or "—"
    optional = f"yes (`{s.optional}`)" if s.optional else "no"
    return f"| `{s.name}` | `{s.container_name or '?'}` | `{s.image or '?'}` | {ports} | {deps} | {optional} |"


def _service_facts(s: Service) -> List[str]:
    ports = (
        ", ".join(f"`{p}`" for p in s.ports)
        if s.ports
        else "none — reachable from the other containers only"
    )
    facts = [
        f"- **Container**: `{s.container_name}`" if s.container_name else None,
        f"- **Image**: `{s.image}`" if s.image else None,
        f"- **Ports published on the machine**: {ports}",
        (
            f"- **Starts after**: {', '.join(f'`{d}`' for d in s.depends_on)}"
            if s.depends_on
            else None
        ),
        (
            f"- **Restart policy**: `{s.restart}` — comes back with Docker after a reboot unless stopped on purpose"
            if s.restart
            else None
        ),
        (
            "- **Healthcheck**: yes — `arcsecond start` waits for it"
            if s.healthcheck
            else None
        ),
        (
            f"- **Time allowed to stop cleanly**: `{s.stop_grace_period}`"
            if s.stop_grace_period
            else None
        ),
        (
            f"- **Storage**: {', '.join(f'`{_esc(v)}`' for v in s.volumes)}"
            if s.volumes
            else None
        ),
        (
            f"- **Reads from .env**: {', '.join(f'[`{v}`](./environment#{v.lower()})' for v in s.env_vars)}"
            if s.env_vars
            else None
        ),
        (
            f"- **Optional**: added with `arcsecond setup --with-{s.optional}`, removed with `--without-{s.optional}`"
            if s.optional
            else None
        ),
    ]
    return [f for f in facts if f]


def render_services(
    services: List[Service], cli_version: str, template_version: Optional[str]
) -> str:
    out = [_frontmatter("Services", cli_version, template_version)]
    out += [
        "# Services",
        "",
        f"What `docker-compose.yml` version {template_version} starts, generated from the file itself — the comments "
        "below are the file's own. `arcsecond status` lists the same services with their state; "
        "`arcsecond logs <service>` shows one's log.",
        "",
        "| Service | Container | Image | Ports on the machine | Depends on | Optional |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    out += [_service_row(s) for s in services]
    out.append("")
    for s in services:
        out += [f"## `{s.name}`", ""]
        if s.description:
            out += [_esc(" ".join(s.description)), ""]
        out += _service_facts(s) + [""]
        if s.notes:
            out += ["From the file:", ""] + [f"> {_esc(n)}" for n in s.notes] + [""]
    return "\n".join(out)


def render_environment(cli_version: str, template_version: Optional[str]) -> str:
    out = [_frontmatter("Environment (.env)", cli_version, template_version)]
    out += [
        "# Environment (.env)",
        "",
        "Every key the `.env` file next to `docker-compose.yml` can hold: the ones `arcsecond setup` writes, "
        "the ones you fill in, and the ones only the backend reads. Compose reads this file and hands the values "
        "to the containers; a container keeps the values it was created with, so after editing it run "
        "`arcsecond restart`.",
        "",
        "::: warning",
        "A `$` in a value is interpolated by compose. Quotes, backslashes and `#` break the parse. Keep values plain.",
        ":::",
        "",
        "| Key | Who sets it | What it is for |",
        "| --- | --- | --- |",
    ]
    for key, (who, what) in ENV_KEYS.items():
        out.append(f"| `{key}` | {who} | {_esc(what)} |")
    out.append("")
    for key, (who, what) in ENV_KEYS.items():
        out += [
            f"## `{key}` {{#{key.lower()}}}",
            "",
            f"*{who.capitalize()}.* {_esc(what)}",
            "",
        ]
    return "\n".join(out)


def generate(cli_version: str) -> dict:
    text = packaged_compose_text()
    version = _compose_version(text)
    services = parse_services(text)
    return {
        "services.md": render_services(services, cli_version, version),
        "environment.md": render_environment(cli_version, version),
    }


__all__ = ["Service", "parse_services", "ENV_KEYS", "generate", "OPTIONAL_SERVICES"]
