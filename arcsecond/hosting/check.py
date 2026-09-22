"""`arcsecond check`: is this installation reachable, and if not, why not.

The failure this exists for is invisible from where the operator sits: the
page does not load from the laptop, and nothing anywhere says why. The
reasons are a short list — the port bound to loopback, the Windows network
marked Public, no firewall rule, HOSTED_FRONTEND_HOST never set, a
third-party security suite — and every one of them can be established from
the machine itself, without administrator rights. So this establishes them,
says which, and prints the exact remedy.

One thing a machine cannot test is its own firewall: a connection to its own
LAN address is not filtered. The firewall verdict therefore comes from reading
the rules, not from probing, and says so.

`--fix` applies the remedy when it can (an elevated shell on Windows) and
prints it otherwise. It never changes the network profile: that changes what
every other program on the machine is exposed to, and is the operator's call.
`--json` is for pasting into a support conversation.
"""

import ctypes
import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import List, Optional

import click

from arcsecond.api.config import ArcsecondConfig
from arcsecond.errors import ArcsecondError
from arcsecond.options import basic_options

from . import stack
from .lifecycle import dir_option
from .local import (
    FRONTEND_HOST_ENV_KEY,
    LOCAL_API_NAME,
    REQUIRED_ENV_PROVIDERS,
    template_versions,
)

OK, WARN, FAIL, SKIP = "ok", "warn", "fail", "skip"

# Addresses that mean "every interface".
EVERYWHERE = {"0.0.0.0", "*", "::", "[::]", "0.0.0.0:", "[::]:"}
LOOPBACK_PREFIXES = ("127.", "[::1]", "::1", "localhost")

FIREWALL_RULE_NAME = "Arcsecond.local (TCP 5555)"
FIREWALL_FIX = (
    f'New-NetFirewallRule -DisplayName "{FIREWALL_RULE_NAME}" -Direction Inbound '
    f"-Protocol TCP -LocalPort {stack.WEB_PORT} -Profile Private -Action Allow"
)
SECRET_KEYS = ("SECRET_KEY", "AUTH_JWT_SIGNING_KEY", "AGENT_JWT_SIGNING_KEY")
HTTP_TIMEOUT = 4.0
POWERSHELL_TIMEOUT = 30.0


@dataclass
class Finding:
    key: str
    label: str
    status: str
    detail: str = ""
    fix: Optional[str] = None
    data: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pure parsers — one per way a platform lists its listening sockets
# ---------------------------------------------------------------------------


def parse_netstat_windows(text: str) -> List[tuple]:
    """`netstat -ano`: `  TCP    0.0.0.0:5555    0.0.0.0:0    LISTENING    4711`."""
    sockets = []
    for line in text.splitlines():
        parts = line.split()
        if (
            len(parts) >= 4
            and parts[0].upper() == "TCP"
            and parts[3].upper() == "LISTENING"
        ):
            sockets.append(_split_endpoint(parts[1]))
    return sockets


def parse_lsof(text: str) -> List[tuple]:
    """`lsof -iTCP -sTCP:LISTEN -P -n`: `... TCP *:5555 (LISTEN)`."""
    sockets = []
    for line in text.splitlines():
        if "(LISTEN)" not in line:
            continue
        match = re.search(r"TCP\s+(\S+)\s+\(LISTEN\)", line)
        if match:
            sockets.append(_split_endpoint(match.group(1)))
    return sockets


def parse_ss(text: str) -> List[tuple]:
    """`ss -ltn`: `LISTEN 0 4096 0.0.0.0:5555 0.0.0.0:*`."""
    sockets = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "LISTEN":
            sockets.append(_split_endpoint(parts[3]))
    return sockets


def _split_endpoint(endpoint: str) -> tuple:
    host, _, port = endpoint.rpartition(":")
    try:
        return host, int(port)
    except ValueError:
        return endpoint, -1


def bound_everywhere(host: str) -> bool:
    return host in EVERYWHERE


def bound_to_loopback(host: str) -> bool:
    return host.startswith(LOOPBACK_PREFIXES)


def parse_powershell_json(text: str) -> list:
    """ConvertTo-Json gives one object for one result, an array for several,
    nothing at all for none."""
    text = (text or "").strip()
    if not text:
        return []
    try:
        loaded = json.loads(text)
    except ValueError:
        return []
    return loaded if isinstance(loaded, list) else [loaded]


def firewall_verdict(rules: list) -> tuple:
    """``(status, detail)`` from the inbound allow rules for the web port.
    Enabled is `1`/`True`/"True" depending on the PowerShell version; Profile
    is a string like "Private" or "Private, Public", or "Any"."""
    for rule in rules:
        enabled = str(rule.get("Enabled", "")).lower() in ("1", "true")
        profiles = str(rule.get("Profile", "")).lower()
        if enabled and (
            "any" in profiles or "private" in profiles or profiles.strip() in ("0", "")
        ):
            return (
                OK,
                f"rule \"{rule.get('DisplayName', '?')}\" allows it ({rule.get('Profile', 'Any')})",
            )
    if rules:
        return (
            FAIL,
            f"{len(rules)} rule(s) found for the port, none enabled for the Private profile",
        )
    return FAIL, f"no inbound rule allows TCP {stack.WEB_PORT}"


def network_profile_verdict(profiles: list) -> tuple:
    """``(status, detail)`` from Get-NetConnectionProfile. NetworkCategory is
    0 Public, 1 Private, 2 Domain (or the word, on newer PowerShell)."""
    if not profiles:
        return WARN, "no active network connection reported"
    public = []
    for p in profiles:
        category = str(p.get("NetworkCategory", "")).lower()
        if category in ("0", "public"):
            public.append(p.get("Name") or p.get("InterfaceAlias") or "?")
    if public:
        return FAIL, f"marked Public: {', '.join(public)}"
    return OK, "every active network is Private (or Domain)"


# ---------------------------------------------------------------------------
# What the machine says
# ---------------------------------------------------------------------------


class Host:
    """The few things asked of the operating system, gathered so tests can
    stand in for it."""

    platform = sys.platform

    def run(
        self, cmd: list, timeout: float = 10.0
    ) -> Optional[subprocess.CompletedProcess]:
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True, check=False, timeout=timeout
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None

    def powershell(self, script: str) -> Optional[str]:
        result = self.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            timeout=POWERSHELL_TIMEOUT,
        )
        if result is None or result.returncode != 0:
            return None
        return result.stdout

    def listening_sockets(self) -> Optional[List[tuple]]:
        if self.platform == "win32":
            result = self.run(["netstat", "-ano"])
            return parse_netstat_windows(result.stdout) if result else None
        if self.platform == "darwin":
            result = self.run(["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"])
            return parse_lsof(result.stdout) if result else None
        result = self.run(["ss", "-ltn"])
        if result is None:
            result = self.run(["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"])
            return parse_lsof(result.stdout) if result else None
        return parse_ss(result.stdout)

    def lan_ipv4(self) -> Optional[str]:
        # No packet is sent: connecting a UDP socket only picks the interface
        # the default route would use, and that is the address to hand around.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                return s.getsockname()[0]
        except OSError:
            return None

    def http_ok(self, url: str) -> Optional[int]:
        try:
            with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as response:
                return response.status
        except urllib.error.HTTPError as e:
            return e.code
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def is_admin(self) -> bool:
        if self.platform != "win32":
            return os.geteuid() == 0 if hasattr(os, "geteuid") else False
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def check_docker(host: Host) -> Finding:
    try:
        version = stack.ensure_docker()
    except ArcsecondError as e:
        return Finding(
            "docker",
            "Docker",
            FAIL,
            str(e).splitlines()[0],
            fix="\n".join(str(e).splitlines()[1:]) or None,
        )
    return Finding("docker", "Docker", OK, f"compose {version}")


def check_template(install) -> Finding:
    current, packaged = template_versions(install)
    if current == packaged:
        return Finding("template", "Compose file", OK, f"version {current}, current")
    return Finding(
        "template",
        "Compose file",
        WARN,
        f"version {current or '?'}; the CLI ships {packaged}",
        fix="arcsecond update",
    )


def check_env_file(install) -> List[Finding]:
    findings = []
    missing = [k for k in REQUIRED_ENV_PROVIDERS if install.read_env(k) is None]
    if missing:
        findings.append(
            Finding(
                "env.keys",
                ".env keys",
                WARN,
                f"missing: {', '.join(missing)}",
                fix="arcsecond setup (adds only what is missing)",
            )
        )
    else:
        findings.append(
            Finding("env.keys", ".env keys", OK, "every key the CLI writes is present")
        )
    dollar = [k for k in SECRET_KEYS if "$" in (install.read_env(k) or "")]
    if dollar:
        findings.append(
            Finding(
                "env.secrets",
                ".env secrets",
                WARN,
                f"'$' in {', '.join(dollar)}: compose interpolates it (the 'variable is not set' warnings)",
                fix="https://docs.arcsecond.io/local/troubleshooting",
            )
        )
    return findings


def check_lan_host(install, host: Host) -> Finding:
    declared = (install.read_env(FRONTEND_HOST_ENV_KEY) or "").strip()
    lan = host.lan_ipv4()
    data = {"declared": declared, "lan_ipv4": lan}
    if not declared or declared.startswith(("localhost", "127.")):
        fix = (
            f"arcsecond setup --lan-host {lan}  &&  arcsecond restart"
            if lan
            else "arcsecond setup --lan-host <this machine's address>  &&  arcsecond restart"
        )
        return Finding(
            "lan.host",
            "Address for other computers",
            WARN,
            "not declared: invitation and password-reset links say localhost",
            fix=fix,
            data=data,
        )
    declared_host = declared.rsplit(":", 1)[0] if ":" in declared else declared
    if (
        lan
        and declared_host.replace("[", "").replace("]", "") != lan
        and re.match(r"^\d+\.\d+\.\d+\.\d+$", declared_host)
    ):
        return Finding(
            "lan.host",
            "Address for other computers",
            WARN,
            f"declared {declared}, but this machine's address is {lan} now (did it change after a reboot?)",
            fix=f"arcsecond setup --lan-host {lan}  &&  arcsecond restart   — or pin the address on the router",
            data=data,
        )
    return Finding(
        "lan.host", "Address for other computers", OK, f"http://{declared}", data=data
    )


def check_containers(install) -> List[Finding]:
    try:
        rows = stack.services_status(install)
    except ArcsecondError as e:
        return [Finding("containers", "Containers", FAIL, str(e).splitlines()[0])]
    if not rows:
        return [
            Finding(
                "containers",
                "Containers",
                FAIL,
                "none exists: the installation has never been started",
                fix="arcsecond start",
            )
        ]
    findings = []
    by_service = {r.get("Service"): r for r in rows}
    for service in ("backend", "web"):
        row = by_service.get(service)
        if row is None:
            findings.append(
                Finding(
                    f"containers.{service}",
                    f"Container {service}",
                    FAIL,
                    "not present",
                    fix="arcsecond start",
                )
            )
            continue
        state = (row.get("State") or "").lower()
        health = (row.get("Health") or "").lower()
        if state == "running" and health in ("", "healthy"):
            findings.append(
                Finding(
                    f"containers.{service}",
                    f"Container {service}",
                    OK,
                    "running" + (f", {health}" if health else ""),
                )
            )
        elif state == "running":
            findings.append(
                Finding(
                    f"containers.{service}",
                    f"Container {service}",
                    WARN,
                    f"running, {health}",
                    fix=f"arcsecond logs {service} --tail 100",
                )
            )
        else:
            findings.append(
                Finding(
                    f"containers.{service}",
                    f"Container {service}",
                    FAIL,
                    state or "?",
                    fix="arcsecond start",
                )
            )
    return findings


def check_ports(host: Host, expect_listening: bool) -> List[Finding]:
    sockets = host.listening_sockets()
    if sockets is None:
        return [
            Finding(
                "ports",
                "Listening ports",
                SKIP,
                "could not list the listening sockets on this platform",
            )
        ]
    findings = []
    for port, name in ((stack.WEB_PORT, "web interface"), (stack.API_PORT, "API")):
        hosts = [h for h, p in sockets if p == port]
        if not hosts:
            status = FAIL if expect_listening else WARN
            findings.append(
                Finding(
                    f"ports.{port}",
                    f"Port {port} ({name})",
                    status,
                    "nothing is listening",
                    fix="arcsecond start" if expect_listening else None,
                    data={"bound": []},
                )
            )
        elif any(bound_everywhere(h) for h in hosts):
            findings.append(
                Finding(
                    f"ports.{port}",
                    f"Port {port} ({name})",
                    OK,
                    "listening on every interface",
                    data={"bound": hosts},
                )
            )
        elif all(bound_to_loopback(h) for h in hosts):
            findings.append(
                Finding(
                    f"ports.{port}",
                    f"Port {port} ({name})",
                    FAIL,
                    f"bound to {', '.join(hosts)} only — reachable from this machine alone",
                    fix="the compose file maps the port as 127.0.0.1:...; `arcsecond update` restores the packaged mapping",
                    data={"bound": hosts},
                )
            )
        else:
            findings.append(
                Finding(
                    f"ports.{port}",
                    f"Port {port} ({name})",
                    OK,
                    f"listening on {', '.join(hosts)}",
                    data={"bound": hosts},
                )
            )
    return findings


def check_answers(host: Host) -> List[Finding]:
    findings = []
    api = host.http_ok(f"http://localhost:{stack.API_PORT}/healthcheck/")
    web = host.http_ok(f"http://localhost:{stack.WEB_PORT}/")
    findings.append(
        Finding(
            "answers.api",
            "Backend answers",
            OK if api == 200 else FAIL,
            f"HTTP {api}" if api else "no answer on localhost",
            fix=None if api == 200 else "arcsecond logs backend --tail 100",
        )
    )
    findings.append(
        Finding(
            "answers.web",
            "Web interface answers",
            OK if web == 200 else FAIL,
            f"HTTP {web}" if web else "no answer on localhost",
            fix=None if web == 200 else "arcsecond logs web --tail 50",
        )
    )
    return findings


def check_windows_network(host: Host) -> Finding:
    out = host.powershell(
        "Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, NetworkCategory | ConvertTo-Json"
    )
    if out is None:
        return Finding(
            "windows.profile",
            "Windows network profile",
            SKIP,
            "PowerShell did not answer",
        )
    status, detail = network_profile_verdict(parse_powershell_json(out))
    fix = None
    if status == FAIL:
        fix = (
            "Settings → Network & Internet → the network's name → Network profile type → Private.\n"
            "Windows blocks incoming connections on a Public network, and a firewall rule "
            "scoped to Private does nothing until this is done."
        )
    return Finding(
        "windows.profile", "Windows network profile", status, detail, fix=fix
    )


def check_windows_firewall(host: Host) -> Finding:
    out = host.powershell(
        "Get-NetFirewallPortFilter -Protocol TCP "
        f"| Where-Object {{ $_.LocalPort -eq '{stack.WEB_PORT}' -or $_.LocalPort -eq 'Any' }} "
        "| Get-NetFirewallRule | Where-Object { $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' } "
        "| Select-Object DisplayName, Enabled, Profile | ConvertTo-Json"
    )
    if out is None:
        return Finding(
            "windows.firewall", "Windows firewall", SKIP, "PowerShell did not answer"
        )
    status, detail = firewall_verdict(parse_powershell_json(out))
    finding = Finding("windows.firewall", "Windows firewall", status, detail)
    if status == FAIL:
        finding.fix = f"In an Administrator PowerShell:\n{FIREWALL_FIX}"
    finding.data["note"] = (
        "Read from the rules, not probed: a machine cannot test its own firewall. "
        "A third-party security suite (Norton, Bitdefender, ESET, Kaspersky…) has a "
        "firewall of its own that this does not see."
    )
    return finding


def fix_windows_firewall(host: Host) -> Finding:
    if not host.is_admin():
        return Finding(
            "windows.firewall.fix",
            "Firewall rule",
            SKIP,
            "not an Administrator shell — run the command above yourself",
        )
    out = host.powershell(FIREWALL_FIX + " | Out-Null; 'ok'")
    if out is None or "ok" not in out:
        return Finding(
            "windows.firewall.fix",
            "Firewall rule",
            FAIL,
            "PowerShell refused to create the rule",
        )
    return Finding(
        "windows.firewall.fix", "Firewall rule", OK, f'created "{FIREWALL_RULE_NAME}"'
    )


def check_proxy() -> List[Finding]:
    from arcsecond.imagesources import autostart
    from arcsecond.imagesources import commands as cameras
    from arcsecond.imagesources import store

    findings = []
    try:
        registered = store.all_cameras()
    except Exception:  # noqa: BLE001 — a corrupt store is its own problem
        registered = []
    port = cameras._running_proxy_port()
    enabled = autostart.is_enabled()
    if not registered:
        findings.append(
            Finding("proxy", "Live-image proxy", SKIP, "no camera registered")
        )
        return findings
    if port is None:
        findings.append(
            Finding(
                "proxy",
                "Live-image proxy",
                WARN,
                f"{len(registered)} camera(s) registered, proxy not running",
                fix="arcsecond proxy start",
            )
        )
    else:
        findings.append(
            Finding(
                "proxy",
                "Live-image proxy",
                OK,
                f"running on port {port}" + (", starts at login" if enabled else ""),
            )
        )
    if enabled:
        env_cameras = [c.id for c in registered if "${" in (c.url or "")]
        if env_cameras:
            findings.append(
                Finding(
                    "proxy.passwords",
                    "Camera passwords",
                    WARN,
                    f"{', '.join(env_cameras)} take a password from an environment variable; "
                    "at login there is no shell to provide it, so they drop",
                    fix="write the password into the URL (`arcsecond webcam add rtsp://user:pass@…`) "
                    "or set the variable for your Windows account",
                )
            )
    return findings


def check_api_pointer() -> Finding:
    current = ArcsecondConfig.current_api_name()
    if current == LOCAL_API_NAME:
        return Finding(
            "api",
            "CLI points at",
            OK,
            f"{current} ({ArcsecondConfig(api_name=current).api_server})",
        )
    if LOCAL_API_NAME in ArcsecondConfig.registered_api_names():
        return Finding(
            "api",
            "CLI points at",
            WARN,
            f"{current} — this installation is registered as '{LOCAL_API_NAME}'",
            fix=f"arcsecond api use {LOCAL_API_NAME}",
        )
    return Finding(
        "api",
        "CLI points at",
        WARN,
        f"{current} — this installation is not registered",
        fix="arcsecond setup (registers it)",
    )


def run_checks(install, host: Host, fix: bool = False) -> List[Finding]:
    findings: List[Finding] = []
    docker = check_docker(host)
    findings.append(docker)
    findings.append(check_template(install))
    findings += check_env_file(install)
    findings.append(check_lan_host(install, host))

    running = False
    if docker.status == OK:
        containers = check_containers(install)
        findings += containers
        running = any(f.key == "containers.web" and f.status == OK for f in containers)
    findings += check_ports(host, expect_listening=running)
    if running:
        findings += check_answers(host)

    if host.platform == "win32":
        findings.append(check_windows_network(host))
        firewall = check_windows_firewall(host)
        findings.append(firewall)
        if fix and firewall.status == FAIL:
            findings.append(fix_windows_firewall(host))

    findings += check_proxy()
    findings.append(check_api_pointer())
    return findings


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------

MARKS = {
    OK: click.style("✓", fg="green"),
    WARN: click.style("!", fg="yellow"),
    FAIL: click.style("✗", fg="red"),
    SKIP: click.style("–", dim=True),
}


def print_findings(findings: List[Finding], install) -> None:
    click.echo(f"Installation: {install.path}\n")
    width = max(len(f.label) for f in findings)
    for f in findings:
        click.echo(f"  {MARKS[f.status]} {f.label.ljust(width)}  {f.detail}")
        if f.fix and f.status in (WARN, FAIL):
            for line in f.fix.splitlines():
                click.echo(f"    {' ' * width}  → {line}")
        note = f.data.get("note")
        if note and f.status != SKIP:
            click.echo(click.style(f"    {' ' * width}  {note}", dim=True))
    fails = sum(1 for f in findings if f.status == FAIL)
    warns = sum(1 for f in findings if f.status == WARN)
    click.echo("")
    if fails:
        click.echo(
            click.style(f"{fails} problem(s), {warns} warning(s).", fg="red", bold=True)
        )
    elif warns:
        click.echo(click.style(f"No problem, {warns} warning(s).", fg="yellow"))
    else:
        click.echo(click.style("Everything checks out.", fg="green", bold=True))
    lan = next((f for f in findings if f.key == "lan.host"), None)
    if lan and lan.data.get("lan_ipv4"):
        click.echo(
            f"\nFrom another computer on this network:  http://{lan.data['lan_ipv4']}:{stack.WEB_PORT}"
        )


@click.command(
    name="check",
    short_help="Check that the installation works, and is reachable from other computers.",
)
@dir_option
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Machine-readable output, for a support conversation.",
)
@click.option(
    "--fix",
    is_flag=True,
    help="Apply the remedies this command can apply itself (the Windows firewall rule, "
    "from an Administrator shell). The network profile is never changed.",
)
@basic_options
def check_cmd(directory, as_json, fix):
    """Run every check an installation can run on itself: Docker, the
    configuration files, the containers, the ports and what they are bound
    to, the address other computers use, and on Windows the network profile
    and the firewall rule. Each problem comes with its remedy.

    Exit code 1 when something fails, 0 otherwise — so it can gate a script.
    """
    install = stack.resolve_install_dir(directory)
    host = Host()
    findings = run_checks(install, host, fix=fix)
    if as_json:
        payload = {
            "installation": str(install.path),
            "platform": host.platform,
            "cli": _cli_version(),
            "findings": [asdict(f) for f in findings],
        }
        click.echo(json.dumps(payload, indent=2))
    else:
        print_findings(findings, install)
    if any(f.status == FAIL for f in findings):
        raise SystemExit(1)


def _cli_version() -> str:
    from arcsecond import __version__

    return __version__.__version__
