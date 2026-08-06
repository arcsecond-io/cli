import os
import re
import sys
from importlib import resources
from pathlib import Path, PurePosixPath, PureWindowsPath

import click

from arcsecond.options import basic_options

from .utils import (
    _get_encryption_key,
    _get_random_postgres_password,
    _get_random_secret_key,
)

ENV_FILENAME = ".env"

# Stable across installs — operators connect with this username when running
# manual psql / pg_dump commands. The actual security boundary is the password
# (generated per-install) and the network exposure (localhost-only).
POSTGRES_USER = "arcsecond_docker"
POSTGRES_DB = "arcsecond_docker"

# Services an installation can opt out of. Each one lives in the packaged
# docker-compose.yml between "# >>> arcsecond:<name>" / "# <<< arcsecond:<name>"
# marker lines, and is added or removed by splicing those blocks as text —
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
    " see https://docs.arcsecond.io/local/transient-alerts"
)


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


def write_env_file():
    env_path = Path.cwd() / ENV_FILENAME
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


def _extract_optional_service_block(packaged_text, name):
    begin, end = _optional_service_markers(name)
    lines = packaged_text.splitlines()
    begin_index = next(
        (i for i, line in enumerate(lines) if line.strip() == begin), None
    )
    end_index = next((i for i, line in enumerate(lines) if line.strip() == end), None)
    if begin_index is None or end_index is None or end_index < begin_index:
        return None
    return lines[begin_index : end_index + 1]


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
    # Drop the blank separator the block carried, so strip(splice(x)) == x.
    if begin_index < len(lines) and not lines[begin_index].strip():
        del lines[begin_index]
    return _with_trailing_newline_like(lines, text)


def _splice_optional_service_block(current_text, packaged_text, name):
    """Insert the packaged block before the top-level "volumes:" line.
    Returns the new text, current_text if the block is already there,
    or None when there is no anchor to splice against."""
    begin, _ = _optional_service_markers(name)
    lines = current_text.splitlines()
    if any(line.strip() == begin for line in lines):
        return current_text
    block = _extract_optional_service_block(packaged_text, name)
    if block is None:
        return None
    anchor = next(
        (
            i
            for i, line in enumerate(lines)
            if line.rstrip() == "volumes:" and not line[:1].isspace()
        ),
        None,
    )
    if anchor is None:
        return None
    new_lines = lines[:anchor] + block + [""] + lines[anchor:]
    return _with_trailing_newline_like(new_lines, current_text)


VERSION_HEADER_RE = re.compile(r"^# Version .+$", flags=re.MULTILINE)


def _compose_version(text):
    match = re.search(r"^# Version (.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _reconcile_version_header(current_text, expected_text):
    """When the *only* remaining difference is the '# Version X.Y' comment
    line, adopt the packaged one — the header is ours, not operator content.
    Without this, every pre-existing install would trail one version behind
    forever and collect a spurious docker-compose.latest.yml on every run.
    Returns the updated text, or None when the files differ beyond it."""
    current_match = VERSION_HEADER_RE.search(current_text)
    expected_match = VERSION_HEADER_RE.search(expected_text)
    if current_match is None or expected_match is None:
        return None
    updated = (
        current_text[: current_match.start()]
        + expected_match.group(0)
        + current_text[current_match.end() :]
    )
    return updated if updated == expected_text else None


def write_docker_compose_file(
    enabled_services=frozenset(), removed_services=frozenset()
) -> Path:
    """
    Materialise the packaged docker-compose.yml in the current directory.

    The expected content is the packaged file minus the marker-delimited
    blocks of optional services that are not enabled. Three cases:
      1. No file present → write the expected content.
      2. File present and identical to the expected content → no-op.
      3. File present but different → splice enabled optional services in
         (idempotently, before the top-level "volumes:" line) and remove
         explicitly-disabled ones; if the file still differs — it carries
         local customisations — leave it untouched and drop the expected
         version next to it as docker-compose.latest.yml so the operator
         can diff and merge intentionally.

    Works from any CWD and when installed from a wheel/sdist.
    """
    dest = Path.cwd() / "docker-compose.yml"

    # arcsecond/hosting/docker/docker-compose.yml
    compose = resources.files("arcsecond.hosting.docker").joinpath("docker-compose.yml")

    with compose.open("rb") as src:
        packaged_text = src.read().decode("utf-8")

    expected_text = packaged_text
    for name in OPTIONAL_SERVICES:
        if name not in enabled_services:
            expected_text = _strip_optional_service_block(expected_text, name)
    expected_content = expected_text.encode("utf-8")

    if not dest.exists():
        dest.write_bytes(expected_content)
        print(f"Wrote docker-compose.yml to: {dest}")
        return dest

    if dest.read_bytes() == expected_content:
        print("docker-compose.yml is already up to date.")
        return dest

    current_text = dest.read_text(encoding="utf-8")
    changes = []
    unspliceable = []

    for name in sorted(enabled_services):
        spliced = _splice_optional_service_block(current_text, packaged_text, name)
        if spliced is None:
            unspliceable.append(name)
        elif spliced != current_text:
            current_text = spliced
            changes.append(f"added the optional '{name}' service")

    for name in sorted(removed_services):
        stripped = _strip_optional_service_block(current_text, name)
        if stripped != current_text:
            current_text = stripped
            changes.append(f"removed the optional '{name}' service")

    if current_text.encode("utf-8") != expected_content:
        reconciled = _reconcile_version_header(current_text, expected_text)
        if reconciled is not None:
            current_text = reconciled
            changes.append(
                f"updated the version header to {_compose_version(expected_text)}"
            )

    if changes:
        dest.write_text(current_text, encoding="utf-8")
        print(f"Updated docker-compose.yml: {', '.join(changes)}.")

    if current_text.encode("utf-8") == expected_content:
        return dest

    current_version = _compose_version(current_text)
    yours = f"Version {current_version}" if current_version else "no Version header"
    latest = dest.with_name("docker-compose.latest.yml")
    latest.write_bytes(expected_content)
    messages = [
        "docker-compose.yml differs from the packaged version "
        f"(yours: {yours}, packaged: Version {_compose_version(expected_text)}); "
        f"leaving it untouched and writing the latest packaged copy to: {latest}"
    ]
    for name in unspliceable:
        messages.append(
            f"Could not find a top-level 'volumes:' line to splice the "
            f"'{name}' service into — merge it from {latest.name} by hand."
        )
    print("\n".join(messages))
    return dest


def _stdin_is_interactive():
    return sys.stdin.isatty()


def _resolve_optional_services(env_path, flags):
    """Fold the explicit flags, the recorded decisions and (on a TTY) the
    operator's answers into (enabled, removed, decisions_to_record)."""
    decisions = _read_optional_service_decisions(env_path)
    enabled, removed, to_record = set(), set(), []
    prompts_skipped = False

    for name, label in OPTIONAL_SERVICES.items():
        flag = flags.get(name)
        if flag is not None:
            # An explicit flag always wins and rewrites the recorded answer.
            (enabled if flag else removed).add(name)
            to_record.append((name, flag))
        elif name in decisions:
            if decisions[name]:
                enabled.add(name)
        elif _stdin_is_interactive():
            answer = click.confirm(
                f"Include the optional {label} service in docker-compose.yml?",
                default=False,
            )
            if answer:
                enabled.add(name)
            to_record.append((name, answer))
        else:
            prompts_skipped = True

    if prompts_skipped:
        print(
            "Skipping optional-service prompts (non-interactive run); "
            "use --with-alerts/--without-alerts to decide."
        )
    return enabled, removed, to_record


@click.command(help="Prepare the installation of Arcsecond.local.")
@click.option(
    "--with-alerts/--without-alerts",
    "with_alerts",
    default=None,
    help="Include (or remove) the optional transient-alerts (ToO) service in "
    "docker-compose.yml without prompting.",
)
@basic_options
def setup(with_alerts):
    click.echo("\nWelcome to Arcsecond.local setup.")
    click.echo(
        "\nThis will write or update two files in this folder (.env and docker-compose.yml)."
    )
    click.echo("")

    env_path = Path.cwd() / ENV_FILENAME
    enabled, removed, to_record = _resolve_optional_services(
        env_path, {"alerts": with_alerts}
    )
    write_env_file()
    for name, answer in to_record:
        _record_optional_service_decision(env_path, name, answer)
    write_docker_compose_file(enabled_services=enabled, removed_services=removed)

    if "alerts" in enabled:
        click.echo(
            "\nTransient alerts next steps: create GCN credentials (see "
            "https://docs.arcsecond.io/local/transient-alerts), paste them into "
            ".env as GCN_CONSUMER_CLIENT_ID / GCN_CONSUMER_CLIENT_SECRET, then "
            "run: docker compose up -d"
        )
