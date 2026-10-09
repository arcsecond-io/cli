import os
import re
import sys
from datetime import datetime
from importlib import resources
from pathlib import Path, PurePosixPath, PureWindowsPath

import click

from arcsecond.api.config import ArcsecondConfig
from arcsecond.errors import ArcsecondError
from arcsecond.options import basic_options

from .utils import (
    _get_encryption_key,
    _get_random_postgres_password,
    _get_random_secret_key,
    _read_env_value,
    _set_env_value,
    lan_ipv4,
)

ENV_FILENAME = ".env"

# Stable across installs — it is the username every `docker exec ... psql`
# in this package and in the docs uses. The actual security boundary is the
# password (generated per-install) and the fact that the database container
# publishes no host port at all.
POSTGRES_USER = "arcsecond_docker"
POSTGRES_DB = "arcsecond_docker"

# Services an installation can opt out of. Each one lives in the packaged
# docker-compose.yml between "# >>> arcsecond:<name>" / "# <<< arcsecond:<name>"
# marker lines; a declined one is cut out of the packaged text as text —
# never by parsing and re-emitting YAML, which would destroy the compose
# file's comments (they are operator documentation).
OPTIONAL_SERVICES = {
    "alerts": "transient-alerts (ToO)",
}

# One .env key records every answered yes/no, e.g. "alerts:yes". A service
# absent from the value has never been decided, so setup may still ask —
# that distinction is what lets a future CLI version introduce a new
# optional service without re-asking about the old ones.
OPTIONAL_SERVICES_ENV_KEY = "ARCSECOND_OPTIONAL_SERVICES"

GCN_ENV_COMMENT = (
    "# NASA GCN credentials (optional — used by the transient-alerts service):"
    " see https://docs.arcsecond.io/guides/operating/transient-alerts"
)

# The address other computers reach this installation at, port included
# (e.g. 192.168.1.42:5555 or arcsecond.local:5555). Empty means localhost:5555,
# which only works on the machine itself. The backend composes invitation and
# password-reset links from it, so it must be what people type in a browser.
FRONTEND_HOST_ENV_KEY = "HOSTED_FRONTEND_HOST"
FRONTEND_HOST_ENV_COMMENT = (
    "# Address other computers use to reach Arcsecond.local, port included"
    " (e.g. 192.168.1.42:5555). Empty = this machine only. See"
    " https://docs.arcsecond.io/start/network"
)

# The name `setup` registers this installation's API under, so that
# `arcsecond api use local` is all it takes to point the CLI at it.
LOCAL_API_NAME = "local"
LOCAL_API_ADDRESS = "http://localhost:8800"


# Compose reads .env itself, and a backslash in a value is an escape sequence
# there — a Windows default like C:\Users\Obs\Data reaches the daemon mangled
# (\U, \O, \D swallowed), and the bind mount then points somewhere that does
# not exist. Windows accepts forward slashes in every path API and Docker
# accepts C:/Users/Obs/Data, so we write the path posix-style on every
# platform. Picked at import time rather than branching inside expand_path so
# tests can exercise the Windows flavour from any host.
_PATH_FLAVOUR = PureWindowsPath if os.name == "nt" else PurePosixPath


def expand_path(value: str) -> str:
    expanded = os.path.expandvars(value)
    expanded = os.path.expanduser(expanded)
    # A backslash is a legal filename character on POSIX, so the conversion
    # must only ever happen with the Windows flavour.
    return _PATH_FLAVOUR(expanded).as_posix()


def prompt_shared_data_path() -> str:
    default_path = str(Path.cwd())

    print("SHARED_DATA_PATH configuration")
    print(f"Default (current folder): {default_path}")
    user_input = input(
        "Press Enter to accept, or type a different path (supports ~ and $VARS): "
    ).strip()

    chosen = user_input if user_input else default_path
    return expand_path(chosen)


# Values are callables so nothing is computed — and no prompt fires — for a
# key that is already present in an existing .env.
REQUIRED_ENV_PROVIDERS = {
    "SECRET_KEY": lambda: _get_random_secret_key(),
    "AUTH_JWT_SIGNING_KEY": lambda: _get_random_secret_key(),
    "AGENT_JWT_SIGNING_KEY": lambda: _get_random_secret_key(),
    "FIELD_ENCRYPTION_KEY": lambda: _get_encryption_key(),
    "SHARED_DATA_PATH": lambda: prompt_shared_data_path(),
    "POSTGRES_USER": lambda: POSTGRES_USER,
    # Per-install random; never overwritten on repeat runs (see write_env_file).
    # Postgres only reads this on first container boot to bootstrap the role,
    # so the .env value and the live DB password must stay in sync — that's
    # why we never regenerate it after the .env exists.
    "POSTGRES_PASSWORD": lambda: _get_random_postgres_password(),
    "POSTGRES_DB": lambda: POSTGRES_DB,
    # Empty placeholders: the operator pastes their own GCN credentials here.
    "GCN_CONSUMER_CLIENT_ID": lambda: "",
    "GCN_CONSUMER_CLIENT_SECRET": lambda: "",
    # Empty placeholder: filled in by `setup` with this machine's LAN address
    # (_fill_in_lan_host), or set by `arcsecond setup --lan-host`, or by hand.
    FRONTEND_HOST_ENV_KEY: lambda: "",
}


def _parse_env_keys(lines):
    keys = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _ = stripped.split("=", 1)
        keys.add(key.strip())
    return keys


def _format_env_line(key, value):
    if key == "SHARED_DATA_PATH":
        return f'{key}="{value}"'
    return f"{key}={value}"


def write_env_file(directory=None):
    env_path = Path(directory or Path.cwd()) / ENV_FILENAME
    ordered_required_keys = [
        "SECRET_KEY",
        "AUTH_JWT_SIGNING_KEY",
        "AGENT_JWT_SIGNING_KEY",
        "FIELD_ENCRYPTION_KEY",
        "SHARED_DATA_PATH",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "GCN_CONSUMER_CLIENT_ID",
        "GCN_CONSUMER_CLIENT_SECRET",
        FRONTEND_HOST_ENV_KEY,
    ]

    def env_lines_for(keys):
        lines = []
        gcn_comment_pending = any(key.startswith("GCN_CONSUMER_") for key in keys)
        for key in keys:
            if key.startswith("GCN_CONSUMER_") and gcn_comment_pending:
                # Once, before whichever GCN key lands first — an operator may
                # have hand-added one of the two already.
                lines.append(GCN_ENV_COMMENT)
                gcn_comment_pending = False
            if key == FRONTEND_HOST_ENV_KEY:
                lines.append(FRONTEND_HOST_ENV_COMMENT)
            lines.append(_format_env_line(key, REQUIRED_ENV_PROVIDERS[key]()))
        return lines

    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()
        existing_keys = _parse_env_keys(existing_lines)
        missing_keys = [
            key for key in ordered_required_keys if key not in existing_keys
        ]

        if not missing_keys:
            print(f"{ENV_FILENAME} already contains all required keys.")
            return

        if existing_lines and existing_lines[-1].strip():
            existing_lines.append("")
        existing_lines.extend(env_lines_for(missing_keys))

        env_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")
        print(
            f"Updated {ENV_FILENAME} at: {env_path} (added keys: {', '.join(missing_keys)})"
        )
        return

    env_contents = "\n".join(env_lines_for(ordered_required_keys))
    env_path.write_text(env_contents + "\n", encoding="utf-8")
    print(f"Wrote {ENV_FILENAME} to: {env_path}")


def _read_optional_service_decisions(env_path):
    """The recorded yes/no answers, as {name: bool}. Unknown names are kept
    out of the dict but preserved in the file (see the recorder)."""
    decisions = {}
    if not env_path.exists():
        return decisions
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith(OPTIONAL_SERVICES_ENV_KEY + "="):
            continue
        _, _, value = stripped.partition("=")
        for token in value.split(","):
            token = token.strip()
            if not token:
                continue
            name, sep, verdict = token.partition(":")
            if not sep or verdict not in ("yes", "no"):
                print(
                    f"Ignoring malformed token '{token}' in {OPTIONAL_SERVICES_ENV_KEY}."
                )
                continue
            if name in OPTIONAL_SERVICES:
                decisions[name] = verdict == "yes"
    return decisions


def _record_optional_service_decision(env_path, name, enabled):
    """Rewrite only this service's token; tokens for services this CLI
    version does not know about survive verbatim (downgrades happen)."""
    verdict = f"{name}:{'yes' if enabled else 'no'}"
    lines = (
        env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    )
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(OPTIONAL_SERVICES_ENV_KEY + "="):
            continue
        _, _, value = stripped.partition("=")
        tokens = [t.strip() for t in value.split(",") if t.strip()]
        tokens = [t for t in tokens if t.partition(":")[0] != name]
        tokens.append(verdict)
        lines[index] = f"{OPTIONAL_SERVICES_ENV_KEY}={','.join(sorted(tokens))}"
        break
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{OPTIONAL_SERVICES_ENV_KEY}={verdict}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _optional_service_markers(name):
    return f"# >>> arcsecond:{name}", f"# <<< arcsecond:{name}"


def _with_trailing_newline_like(lines, original_text):
    return "\n".join(lines) + ("\n" if original_text.endswith("\n") else "")


def _strip_optional_service_block(text, name):
    begin, end = _optional_service_markers(name)
    lines = text.splitlines()
    begin_index = next(
        (i for i, line in enumerate(lines) if line.strip() == begin), None
    )
    end_index = next((i for i, line in enumerate(lines) if line.strip() == end), None)
    if begin_index is None or end_index is None or end_index < begin_index:
        return text
    del lines[begin_index : end_index + 1]
    # Drop the blank separator the block carried, so the file reads the same
    # as if the service had never been there.
    if begin_index < len(lines) and not lines[begin_index].strip():
        del lines[begin_index]
    return _with_trailing_newline_like(lines, text)


def _compose_carries_service(text, name):
    """Whether a compose file runs this optional service — between our
    markers, or added by hand under its fixed container name."""
    begin, _ = _optional_service_markers(name)
    return any(line.strip() == begin for line in text.splitlines()) or (
        f"container_name: arcsecond-{name}" in text
    )


def _compose_version(text):
    match = re.search(r"^# Version (.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _expected_compose_text(packaged_text: str, enabled_services) -> str:
    """The packaged file minus every optional service that is not enabled."""
    text = packaged_text
    for name in OPTIONAL_SERVICES:
        if name not in enabled_services:
            text = _strip_optional_service_block(text, name)
    return text


def packaged_compose_text() -> str:
    # arcsecond/hosting/docker/docker-compose.yml
    compose = resources.files("arcsecond.hosting.docker").joinpath("docker-compose.yml")
    with compose.open("rb") as src:
        # LF whatever the checkout did (.gitattributes asks for LF, belt and braces).
        return src.read().decode("utf-8").replace("\r\n", "\n")


def template_versions(install):
    """``(installed, packaged)`` compose template versions, for `status`.
    ``installed`` is None when the file has no version header."""
    try:
        current = _compose_version(install.compose_path.read_text(encoding="utf-8"))
    except OSError:
        current = None
    return current, _compose_version(packaged_compose_text())


COMPOSE_OVERRIDE_FILENAME = "docker-compose.override.yml"

# What CLIs before 4.4 wrote beside an edited docker-compose.yml, for the
# operator to merge by hand. Nothing reads it any more.
STALE_LATEST_FILENAME = "docker-compose.latest.yml"


def _backup_path(dest: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = dest.with_name(f"docker-compose.backup-{stamp}.yml")
    counter = 2
    while candidate.exists():
        candidate = dest.with_name(f"docker-compose.backup-{stamp}-{counter}.yml")
        counter += 1
    return candidate


def write_docker_compose_file(enabled_services=frozenset(), directory=None) -> Path:
    """Make docker-compose.yml exactly the packaged one, with the enabled
    optional services and without the others.

    The file belongs to the CLI: it is what makes an installation the one
    this version of the CLI knows how to run, so `setup` and `update` always
    leave it current. A file that differs — an older template, a service
    missing, an edit by hand — is moved aside as
    docker-compose.backup-<date>-<time>.yml first, so nothing is lost. Local
    changes that must survive updates go in docker-compose.override.yml,
    which compose layers on top and the CLI never touches.

    Works from any CWD and when installed from a wheel/sdist.
    """
    dest = Path(directory or Path.cwd()) / "docker-compose.yml"
    expected_text = _expected_compose_text(packaged_compose_text(), enabled_services)
    expected_version = _compose_version(expected_text)

    stale_latest = dest.with_name(STALE_LATEST_FILENAME)
    if stale_latest.exists():
        stale_latest.unlink()
        print(f"Removed {STALE_LATEST_FILENAME}, which is no longer used.")

    if not dest.exists():
        dest.write_bytes(expected_text.encode("utf-8"))
        print(f"Wrote docker-compose.yml (version {expected_version}) to: {dest}")
        return dest

    # Text, not bytes: a file written on Windows may carry CRLF and still be
    # the packaged content.
    current_text = dest.read_text(encoding="utf-8")
    if current_text == expected_text:
        print(f"docker-compose.yml is up to date (version {expected_version}).")
        return dest

    backup = _backup_path(dest)
    dest.replace(backup)
    dest.write_bytes(expected_text.encode("utf-8"))

    current_version = _compose_version(current_text)
    was = f"version {current_version}" if current_version else "no version header"
    print(
        f"Replaced docker-compose.yml with version {expected_version} (it had {was}).\n"
        f"The previous file is kept as {backup.name}. If you had changed it by "
        f"hand, put those changes in {COMPOSE_OVERRIDE_FILENAME}: compose applies "
        "it on top, and the CLI never touches it."
    )
    return dest


def _stdin_is_interactive():
    return sys.stdin.isatty()


def _decide_optional_service(name, label, flag, decisions, current_compose):
    """``(enabled, record)`` for one service; ``enabled`` is None when nobody
    decided and there is no terminal to ask on. ``record`` says whether the
    answer goes into .env."""
    if flag is not None:
        # An explicit flag always wins and rewrites the recorded answer.
        return flag, True
    if name in decisions:
        return decisions[name], False
    if _compose_carries_service(current_compose, name):
        # Installed before decisions were recorded, or added by hand: the
        # service runs today, and rewriting the file must not drop it.
        return True, True
    if _stdin_is_interactive():
        answer = click.confirm(
            f"Include the optional {label} service in docker-compose.yml?",
            default=False,
        )
        return answer, True
    return None, False


def _resolve_optional_services(env_path, flags, compose_path=None):
    """Fold the explicit flags, the recorded decisions, what the current
    compose file already runs, and (on a TTY) the operator's answers into
    (enabled, decisions_to_record)."""
    decisions = _read_optional_service_decisions(env_path)
    try:
        current_compose = (
            compose_path.read_text(encoding="utf-8") if compose_path else ""
        )
    except OSError:
        current_compose = ""
    enabled, to_record = set(), []
    prompts_skipped = False

    for name, label in OPTIONAL_SERVICES.items():
        answer, record = _decide_optional_service(
            name, label, flags.get(name), decisions, current_compose
        )
        if answer is None:
            prompts_skipped = True
            continue
        if answer:
            enabled.add(name)
        if record:
            to_record.append((name, answer))

    if prompts_skipped:
        print(
            "Skipping optional-service prompts (non-interactive run); "
            "use --with-alerts/--without-alerts to decide."
        )
    return enabled, to_record


def _register_local_api():
    """Make `arcsecond api use local` possible without a registration step.
    Never overwrites an address the operator set themselves."""
    config = ArcsecondConfig(api_name=LOCAL_API_NAME)
    if not (config.api_server or "").strip():
        config.api_server = LOCAL_API_ADDRESS


def _offer_token():
    """Ask for the observatory's access token, once, so that `start` can
    download the images. Skipped when Docker already holds it, when Docker is
    not reachable yet (the message says what to do instead), and when there is
    no terminal to ask on."""
    from . import stack, token

    try:
        stack.ensure_docker()
    except ArcsecondError:
        click.echo(
            "\nDocker is not reachable right now. Once it is, enter the access token "
            "Arcsecond gave your observatory:  arcsecond token set"
        )
        return
    if token.has_token():
        return
    if not _stdin_is_interactive():
        click.echo(
            "\nThis machine has no access token yet. Enter it with:  arcsecond token set"
        )
        return
    click.echo("\n" + token.WHAT_IT_IS)
    click.echo("Leave it empty to do this later with `arcsecond token set`.")
    entered = click.prompt(
        "Access token from Arcsecond (nothing is shown while you type)",
        hide_input=True,
        default="",
        show_default=False,
    ).strip()
    if not entered:
        click.echo("Skipped. Before `arcsecond start`:  arcsecond token set")
        return
    token.store_token(entered)
    click.echo(click.style("Token accepted.", fg="green"))


def _offer_sky_map(env_path, flag):
    from . import skybrightness

    skybrightness.offer(env_path, flag=flag, interactive=_stdin_is_interactive())


def _normalise_lan_host(value):
    """`192.168.1.42` → `192.168.1.42:5555`; a scheme or a path is refused."""
    value = (value or "").strip()
    if not value:
        return ""
    if "://" in value or "/" in value:
        raise click.BadParameter(
            "give the host and port only, without scheme or path — e.g. "
            "192.168.1.42:5555 or arcsecond.local:5555"
        )
    if ":" not in value:
        value = f"{value}:5555"
    return value


# What `--lan-host ""` writes. Spelled out rather than left empty, so that the
# next `setup` does not take an empty value for "never decided" and declare the
# LAN address over the operator's choice.
THIS_MACHINE_ONLY_HOST = "localhost:5555"


def _fill_in_lan_host(env_path):
    """Declare this machine's LAN address when no address is declared yet.

    Left empty, every invitation and password-reset link the server emails
    says localhost, which only works on this machine. A value already there,
    whoever wrote it, is never touched: `doctor` is what notices when a
    declared IP no longer matches the machine.
    """
    if (_read_env_value(FRONTEND_HOST_ENV_KEY, env_path) or "").strip():
        return None
    detected = lan_ipv4()
    if not detected or detected.startswith("127."):
        return None
    host = _normalise_lan_host(detected)
    _set_env_value(env_path, FRONTEND_HOST_ENV_KEY, host)
    return host


@click.command(short_help="Prepare the installation of Arcsecond.local.")
@click.option(
    "--with-alerts/--without-alerts",
    "with_alerts",
    default=None,
    help="Include (or remove) the optional transient-alerts (ToO) service in "
    "docker-compose.yml without prompting.",
)
@click.option(
    "--lan-host",
    "lan_host",
    default=None,
    metavar="HOST[:PORT]",
    help="The address other computers reach this machine at (e.g. "
    "192.168.1.42 or arcsecond.local). Needed for invitation and "
    "password-reset links to work from other computers. Port defaults to 5555. "
    "Without it, setup declares this machine's network address when none is "
    "declared yet; an empty value keeps the links on this machine.",
)
@click.option(
    "--with-sky-map/--without-sky-map",
    "with_sky_map",
    default=None,
    help="Keep (or not) a copy of the sky-brightness map on this machine, "
    "without prompting. With a copy, no outside lookup is made for it.",
)
@basic_options
def setup(with_alerts, lan_host, with_sky_map):
    """Write (or update) the two files an installation is made of, in the
    current folder: .env, with this installation's secrets, and
    docker-compose.yml — and ask for the access token Arcsecond gave your
    observatory, if this machine has none yet. Then:  arcsecond start

    Run again, it keeps .env and its secrets, and brings docker-compose.yml
    up to date; a file that differed is kept aside as a backup.
    """
    click.echo("\nWelcome to Arcsecond.local setup.")
    click.echo(
        "\nThis will write or update two files in this folder (.env and docker-compose.yml)."
    )
    click.echo("")

    directory = Path.cwd()
    env_path = directory / ENV_FILENAME
    enabled, to_record = _resolve_optional_services(
        env_path, {"alerts": with_alerts}, compose_path=directory / "docker-compose.yml"
    )
    write_env_file(directory=directory)
    for name, answer in to_record:
        _record_optional_service_decision(env_path, name, answer)
    if lan_host is not None:
        host = _normalise_lan_host(lan_host) or THIS_MACHINE_ONLY_HOST
        _set_env_value(env_path, FRONTEND_HOST_ENV_KEY, host)
        if host != THIS_MACHINE_ONLY_HOST:
            print(f"Other computers will reach this installation at http://{host}")
        else:
            print("This installation is reachable from this machine only.")
    else:
        host = _fill_in_lan_host(env_path)
        if host:
            print(
                f"Other computers will reach this installation at http://{host}"
                " (this machine's network address; change it with --lan-host)"
            )
    write_docker_compose_file(enabled_services=enabled, directory=directory)

    from .stack import remember_install_dir

    remember_install_dir(directory)
    _register_local_api()
    _offer_token()
    _offer_sky_map(env_path, with_sky_map)

    if "alerts" in enabled:
        click.echo(
            "\nTransient alerts next steps: create GCN credentials (see "
            "https://docs.arcsecond.io/guides/operating/transient-alerts), paste them into "
            ".env as GCN_CONSUMER_CLIENT_ID / GCN_CONSUMER_CLIENT_SECRET, then "
            "run: arcsecond restart alerts"
        )

    click.echo("\nNext:  " + click.style("arcsecond start", bold=True))
