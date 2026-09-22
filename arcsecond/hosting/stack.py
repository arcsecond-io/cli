"""The Arcsecond.local install directory, and Docker Compose driven from Python.

Everything an operator used to type as `docker compose ...` goes through here,
so that the lifecycle commands (`start`, `stop`, `status`...) agree on where
the installation is, how Docker is reached, and what its failures mean.

An installation is a directory holding the two files `arcsecond setup` writes,
docker-compose.yml and .env. Commands find it in this order: the `--dir`
option; the current directory; the directory `setup` last ran in, which it
records in config.ini. The third one is what lets `arcsecond start` work from
a PowerShell opened in the home folder — the default on Windows.
"""

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from arcsecond.api.config import ArcsecondConfig
from arcsecond.errors import ArcsecondError

from .utils import _read_env_value

COMPOSE_FILENAME = "docker-compose.yml"
ENV_FILENAME = ".env"

CLI_KEY_INSTALL_DIR = "install_dir"

# Fixed by the packaged compose template (container_name), so a container can
# be inspected without asking compose first.
API_CONTAINER = "arcsecond-api"

WEB_PORT = 5555
API_PORT = 8800

DOCKER_INFO_TIMEOUT = 20.0  # seconds; Docker Desktop mid-startup hangs the client
BACKEND_WAIT_TIMEOUT = 300.0  # the first boot loads timezones, exoplanets...
BACKEND_POLL_INTERVAL = 3.0


# ---------------------------------------------------------------------------
# The install directory
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstallDir:
    path: Path

    @property
    def compose_path(self) -> Path:
        return self.path / COMPOSE_FILENAME

    @property
    def env_path(self) -> Path:
        return self.path / ENV_FILENAME

    def read_env(self, key: str) -> Optional[str]:
        return _read_env_value(key, self.env_path)


def _holds_an_install(path: Path) -> bool:
    return (path / COMPOSE_FILENAME).is_file()


def remember_install_dir(path: Path) -> None:
    ArcsecondConfig.write_cli_setting(CLI_KEY_INSTALL_DIR, str(Path(path).resolve()))


def remembered_install_dir() -> Optional[Path]:
    recorded = ArcsecondConfig.read_cli_setting(CLI_KEY_INSTALL_DIR)
    return Path(recorded) if recorded else None


def resolve_install_dir(explicit: Optional[str] = None) -> InstallDir:
    """Where the installation is, or an error that says where was looked."""
    if explicit:
        path = Path(explicit).expanduser()
        if not _holds_an_install(path):
            raise ArcsecondError(
                f"No Arcsecond.local installation in {path}: there is no "
                f"{COMPOSE_FILENAME} there. Run `arcsecond setup` in that folder first."
            )
        return InstallDir(path.resolve())

    cwd = Path.cwd()
    if _holds_an_install(cwd):
        return InstallDir(cwd.resolve())

    remembered = remembered_install_dir()
    if remembered is not None and _holds_an_install(remembered):
        return InstallDir(remembered.resolve())

    tried = [f"  - the current folder: {cwd}"]
    if remembered is not None:
        tried.append(f"  - the folder `arcsecond setup` last ran in: {remembered}")
    raise ArcsecondError(
        "Could not find an Arcsecond.local installation. Looked in:\n"
        + "\n".join(tried)
        + f"\n\nAn installation is a folder holding {COMPOSE_FILENAME} and {ENV_FILENAME}, "
        "written by `arcsecond setup`. Run that first, or point at the folder "
        "with --dir."
    )


# ---------------------------------------------------------------------------
# Reaching Docker
# ---------------------------------------------------------------------------

DOCKER_NOT_INSTALLED = (
    "Docker is not installed, or not on the PATH of this terminal.\n"
    "Install Docker Desktop (Windows, macOS) or Docker Engine (Linux), then open "
    "a new terminal."
)
DOCKER_NOT_RUNNING = (
    "Docker is installed but its daemon is not running.\n"
    "Start Docker Desktop and wait for the whale icon to settle, then try again."
)
DOCKER_NOT_ANSWERING = (
    "Docker is not answering. Docker Desktop is probably still starting — give "
    "it a minute and try again."
)
DOCKER_PERMISSION = (
    "This user is not allowed to talk to Docker.\n"
    "On Linux, add yourself to the docker group and log out and back in:\n"
    "    sudo usermod -aG docker $USER"
)
COMPOSE_MISSING = (
    "Docker is running, but `docker compose` (v2) is not available.\n"
    "Docker Desktop ships it; on Docker Engine install the docker-compose-plugin "
    "package."
)


def _run(cmd, timeout=None, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, check=False, timeout=timeout, **kwargs
    )


def ensure_docker() -> str:
    """Raise a plain-language error unless Docker and compose v2 are usable.
    Returns the compose version, for `status`."""
    if shutil.which("docker") is None:
        raise ArcsecondError(DOCKER_NOT_INSTALLED)
    try:
        info = _run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            timeout=DOCKER_INFO_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise ArcsecondError(DOCKER_NOT_ANSWERING) from None
    if info.returncode != 0:
        stderr = (info.stderr or "").lower()
        if "permission denied" in stderr:
            raise ArcsecondError(DOCKER_PERMISSION)
        raise ArcsecondError(DOCKER_NOT_RUNNING)
    try:
        compose = _run(
            ["docker", "compose", "version", "--short"], timeout=DOCKER_INFO_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        raise ArcsecondError(DOCKER_NOT_ANSWERING) from None
    if compose.returncode != 0:
        raise ArcsecondError(COMPOSE_MISSING)
    return (compose.stdout or "").strip()


# ---------------------------------------------------------------------------
# Driving compose
# ---------------------------------------------------------------------------


def compose_command(install: InstallDir, *args: str) -> list:
    # --project-directory is where compose reads .env from; -f pins the file so
    # a docker-compose.override.yml an operator may have added still applies.
    return [
        "docker",
        "compose",
        "--project-directory",
        str(install.path),
        "-f",
        str(install.compose_path),
        *args,
    ]


def compose(
    install: InstallDir, *args: str, timeout=None
) -> subprocess.CompletedProcess:
    """Run one compose command, output captured."""
    return _run(compose_command(install, *args), timeout=timeout, cwd=str(install.path))


def compose_streaming(
    install: InstallDir, *args: str, echo: Optional[Callable[[str], None]] = None
) -> subprocess.CompletedProcess:
    """Run one compose command, showing its progress as it goes.

    Compose narrates on stderr — image pulls, containers created — and a first
    `up` downloads for minutes with nothing else to look at, so that stream is
    relayed line by line. Its tail is kept too, so a failure can still be
    explained after the fact (see ``explain_compose_failure``).
    """
    cmd = compose_command(install, *args)
    process = subprocess.Popen(
        cmd,
        cwd=str(install.path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
    )
    tail = []
    assert process.stderr is not None
    for line in process.stderr:
        line = line.rstrip("\n")
        if echo is not None:
            echo(line)
        tail.append(line)
        if len(tail) > 60:
            del tail[0]
    process.wait()
    return subprocess.CompletedProcess(
        cmd, process.returncode, stdout="", stderr="\n".join(tail)
    )


# The compose failures the troubleshooting page used to explain, matched on
# the daemon's own words so `start` can answer them on the spot.
_KNOWN_FAILURES = (
    (
        (
            "ports are not available",
            "address already in use",
            "port is already allocated",
        ),
        "A port Arcsecond.local needs is taken by something else on this machine.\n"
        f"Port {WEB_PORT} is the web interface and {API_PORT} the API; 8900 is the plate "
        "solver. Find what holds it (`netstat -ano | findstr :PORT` on Windows, "
        "`lsof -i :PORT` elsewhere) and stop it, or check with `docker ps` for a "
        "container left over from an older installation.",
    ),
    (
        ("permission denied while trying to connect",),
        DOCKER_PERMISSION,
    ),
    (
        ("cannot connect to the docker daemon", "is the docker daemon running"),
        DOCKER_NOT_RUNNING,
    ),
    (
        ("is already in use by container",),
        "A container with that name already exists on this machine, from another "
        "Arcsecond installation (an older folder, or a development setup). Either "
        "start *that* installation from its own folder, or remove the leftover "
        "container: `docker rm -f <name>` with the name Docker printed above.",
    ),
    (
        ("no such service",),
        "That service is not in your docker-compose.yml. `arcsecond status` lists "
        "the ones that are; optional services are added with `arcsecond setup "
        "--with-<name>`.",
    ),
    (
        ("denied", "unauthorized", "pull access denied"),
        "Docker could not download an Arcsecond image: the registry refused.\n"
        "Enter the token Arcsecond gave your observatory:  arcsecond token set",
    ),
)


def explain_compose_failure(stderr: str) -> Optional[str]:
    """A plain-language explanation of a failed compose run, if it is a known one."""
    haystack = (stderr or "").lower()
    for needles, explanation in _KNOWN_FAILURES:
        if any(needle in haystack for needle in needles):
            return explanation
    return None


def raise_compose_failure(what: str, result: subprocess.CompletedProcess) -> None:
    explanation = explain_compose_failure(result.stderr)
    lines = [f"`{what}` failed (exit code {result.returncode})."]
    if explanation:
        lines += ["", explanation]
    detail = (result.stderr or "").strip()
    if detail and not explanation:
        lines += ["", "Docker said:", detail]
    raise ArcsecondError("\n".join(lines))


# ---------------------------------------------------------------------------
# What is running
# ---------------------------------------------------------------------------


def _parse_json_lines(text: str) -> list:
    """Compose prints `--format json` as one array on older releases and as
    one object per line since 2.21. Accept both."""
    text = (text or "").strip()
    if not text:
        return []
    try:
        loaded = json.loads(text)
        return loaded if isinstance(loaded, list) else [loaded]
    except ValueError:
        pass
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except ValueError:
            continue
    return items


def services_status(install: InstallDir) -> list:
    """One dict per container compose knows of, running or not.
    Keys used downstream: Service, State, Health, Image, Name."""
    result = compose(install, "ps", "-a", "--format", "json")
    if result.returncode != 0:
        raise_compose_failure("docker compose ps", result)
    return _parse_json_lines(result.stdout)


def declared_services(install: InstallDir) -> list:
    result = compose(install, "config", "--services")
    if result.returncode != 0:
        return []
    return [s.strip() for s in result.stdout.splitlines() if s.strip()]


def container_state(name: str):
    """``(running, health)`` for a container, ``(None, None)`` when absent.
    ``health`` is 'healthy', 'unhealthy', 'starting' or None (no healthcheck)."""
    result = _run(
        [
            "docker",
            "inspect",
            "-f",
            "{{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
            name,
        ]
    )
    if result.returncode != 0:
        return None, None
    parts = (result.stdout or "").strip().split()
    if len(parts) != 2:
        return None, None
    running = parts[0] == "true"
    health = None if parts[1] == "none" else parts[1]
    return running, health


def wait_for_backend(
    timeout: float = BACKEND_WAIT_TIMEOUT,
    poll: float = BACKEND_POLL_INTERVAL,
    tick: Optional[Callable[[], None]] = None,
    clock=time.monotonic,
    sleep=time.sleep,
) -> Optional[str]:
    """Poll the API container until its healthcheck passes.

    Returns None when it did, or a reason it did not: 'unhealthy', 'missing',
    or 'timeout'. The container restarting on its own (unless-stopped) is
    waited through rather than treated as a failure.
    """
    deadline = clock() + timeout
    while clock() < deadline:
        running, health = container_state(API_CONTAINER)
        if running is None:
            return "missing"
        if health == "healthy":
            return None
        if health == "unhealthy":
            return "unhealthy"
        if tick is not None:
            tick()
        sleep(poll)
    return "timeout"


def frontend_addresses(install: InstallDir) -> list:
    """The URLs the web interface answers at: always localhost, plus the LAN
    address declared in .env when there is one."""
    addresses = [f"http://localhost:{WEB_PORT}"]
    declared = (install.read_env("HOSTED_FRONTEND_HOST") or "").strip()
    if declared and declared != f"localhost:{WEB_PORT}":
        scheme = (
            install.read_env("HOSTED_FRONTEND_SCHEME") or "http"
        ).strip() or "http"
        addresses.append(f"{scheme}://{declared}")
    return addresses
