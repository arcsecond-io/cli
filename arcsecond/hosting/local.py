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


def write_env_file():
    secret_key = _get_random_secret_key()
    field_encryption_key = _get_encryption_key()
    shared_data_path = prompt_shared_data_path()

    env_contents = "\n".join(
        [
            f"SECRET_KEY={secret_key}",
            f"FIELD_ENCRYPTION_KEY={field_encryption_key}",
            f'SHARED_DATA_PATH="{shared_data_path}"',
            f"POSTGRES_USER={POSTGRES_USER}",
            f"POSTGRES_PASSWORD={POSTGRES_PASSWORD}",
            f"POSTGRES_DB={POSTGRES_DB}",
            "",
        ]
    )

    env_path = Path.cwd() / ENV_FILENAME
    env_path.write_text(env_contents, encoding="utf-8")
    print(f"Wrote {ENV_FILENAME} to: {env_path}")


def write_docker_compose_file() -> Path:
    """
    Copy the packaged docker-compose.yml to the current directory.
    Works from any CWD and when installed from a wheel/sdist.
    """
    dest = Path.cwd() / "docker-compose.yml"

    # arcsecond/hosting/docker/docker-compose.yml
    compose = resources.files("arcsecond.hosting.docker").joinpath("docker-compose.yml")

    with compose.open("rb") as src, dest.open("wb") as dst:
        dst.write(src.read())

    return dest


@click.command(help="Prepare the installation of Arcsecond.local.")
@basic_options
def setup():
    click.echo("\nWelcome to Arcsecond.local setup.")
    click.echo("\nThis will write two new files in this folder (.env and docker-compose.yml),")
    click.echo("as well as asking you one question where to store the data.\n")
    write_env_file()
    write_docker_compose_file()
