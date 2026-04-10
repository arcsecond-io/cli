import os
from importlib import resources
from pathlib import Path

import click

from arcsecond.options import basic_options
from .utils import _get_encryption_key, _get_random_secret_key

ENV_FILENAME = ".env"

POSTGRES_USER = "arcsecond_docker"
POSTGRES_PASSWORD = "arcsecond_docker"
POSTGRES_DB = "arcsecond_docker"


def expand_path(value: str) -> str:
    expanded = os.path.expandvars(value)
    expanded = os.path.expanduser(expanded)
    return str(Path(expanded))


def prompt_shared_data_path() -> str:
    default_path = str(Path.cwd())

    print("SHARED_DATA_PATH configuration")
    print(f"Default (current folder): {default_path}")
    user_input = input("Press Enter to accept, or type a different path (supports ~ and $VARS): ").strip()

    chosen = user_input if user_input else default_path
    return expand_path(chosen)


def _required_env_values():
    return {
        "SECRET_KEY": _get_random_secret_key(),
        "AUTH_JWT_SIGNING_KEY": _get_random_secret_key(),
        "AGENT_JWT_SIGNING_KEY": _get_random_secret_key(),
        "FIELD_ENCRYPTION_KEY": _get_encryption_key(),
        "SHARED_DATA_PATH": prompt_shared_data_path(),
        "POSTGRES_USER": POSTGRES_USER,
        "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
        "POSTGRES_DB": POSTGRES_DB,
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
    required_values = _required_env_values()
    ordered_required_keys = [
        "SECRET_KEY",
        "AUTH_JWT_SIGNING_KEY",
        "AGENT_JWT_SIGNING_KEY",
        "FIELD_ENCRYPTION_KEY",
        "SHARED_DATA_PATH",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ]

    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()
        existing_keys = _parse_env_keys(existing_lines)
        missing_keys = [key for key in ordered_required_keys if key not in existing_keys]

        if not missing_keys:
            print(f"{ENV_FILENAME} already contains all required keys.")
            return

        if existing_lines and existing_lines[-1].strip():
            existing_lines.append("")
        for key in missing_keys:
            existing_lines.append(_format_env_line(key, required_values[key]))

        env_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")
        print(
            f"Updated {ENV_FILENAME} at: {env_path} (added keys: {', '.join(missing_keys)})"
        )
        return

    env_contents = "\n".join(
        [_format_env_line(key, required_values[key]) for key in ordered_required_keys]
    )
    env_path.write_text(env_contents + "\n", encoding="utf-8")
    print(f"Wrote {ENV_FILENAME} to: {env_path}")


def write_docker_compose_file() -> Path:
    """
    Copy the packaged docker-compose.yml to the current directory.
    Works from any CWD and when installed from a wheel/sdist.
    """
    dest = Path.cwd() / "docker-compose.yml"

    # arcsecond/hosting/docker/docker-compose.yml
    compose = resources.files("arcsecond.hosting.docker").joinpath("docker-compose.yml")

    with compose.open("rb") as src:
        expected_content = src.read()

    if not dest.exists():
        dest.write_bytes(expected_content)
        print(f"Wrote docker-compose.yml to: {dest}")
        return dest

    current_content = dest.read_bytes()
    if current_content == expected_content:
        print("docker-compose.yml is already up to date.")
        return dest

    dest.write_bytes(expected_content)
    print("docker-compose.yml has been updated to the latest version.")
    return dest


@click.command(help="Prepare the installation of Arcsecond.local.")
@basic_options
def setup():
    click.echo("\nWelcome to Arcsecond.local setup.")
    click.echo("\nThis will write two new files in this folder (.env and docker-compose.yml),")
    click.echo("as well as asking you one question where to store the data.\n")
    write_env_file()
    write_docker_compose_file()
