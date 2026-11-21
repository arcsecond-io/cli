"""`arcsecond disks`: the disks of this machine Arcsecond.local can attach as
"Local Disk" storages.

The containers see nothing of the machine but the data folder, so a disk has
to be mounted into them before the web interface can attach a folder of it.
The CLI does that in a file of its own beside docker-compose.yml,
docker-compose.disks.yml, which it names to compose with the others (see
stack.compose_command): one bind mount per disk, at /disks/<name>, on the
services that read and write storages. The operator never edits it, nor .env.

`setup` and `update` ask once whether there is a disk to attach; the answer
"no" is remembered in .env (LOCAL_DISKS_ENV_KEY) so that the question is not
asked again. `arcsecond disks add/remove/list` change things afterwards.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict

import click

from arcsecond.errors import ArcsecondError
from arcsecond.options import basic_options

from . import stack

DISKS_COMPOSE_FILENAME = "docker-compose.disks.yml"

# Where the backend looks for disks (ARCSECOND_DISKS_ROOT backend-side).
DISKS_TARGET = "/disks"

# The services that read and write attached storages: the API (connection
# tests, folder browsing) and both workers (scans, pushes).
DISK_SERVICES = ("backend", "worker", "dataworker")

# "no" once the operator declined the question, so that `update` stops asking.
LOCAL_DISKS_ENV_KEY = "ARCSECOND_LOCAL_DISKS"

_NAME_RE = re.compile(r"[^a-z0-9._-]+")
_PAIR_RE = re.compile(r'source:\s*(".*")\s*\n\s*target:\s*/disks/([A-Za-z0-9._-]+)')


def disks_compose_path(install) -> Path:
    return install.path / DISKS_COMPOSE_FILENAME


def disk_name(path: str, taken=()) -> str:
    """A name for /disks/<name>: the folder's own, lowercased, made safe, and
    made unique among the names already taken."""
    base = _NAME_RE.sub("-", Path(path.rstrip("/\\")).name.lower()).strip("-.") or "disk"
    name, index = base, 2
    while name in taken:
        name, index = f"{base}-{index}", index + 1
    return name


def _compose_quote(path: str) -> str:
    # A JSON string is a YAML double-quoted scalar; `$` is compose's
    # interpolation sign and doubles to stay literal.
    return json.dumps(path.replace("$", "$$"))


def read_disks(install) -> Dict[str, str]:
    """{name: host path} of the disks mounted today, from the CLI's own file."""
    path = disks_compose_path(install)
    if not path.is_file():
        return {}
    disks = {}
    for quoted, name in _PAIR_RE.findall(path.read_text(encoding="utf-8")):
        try:
            disks.setdefault(name, json.loads(quoted).replace("$$", "$"))
        except ValueError:
            continue
    return disks


def write_disks(install, disks: Dict[str, str]) -> None:
    """Rewrite docker-compose.disks.yml for these disks, or remove it when
    there is none left."""
    path = disks_compose_path(install)
    if not disks:
        if path.exists():
            path.unlink()
        return
    lines = [
        "# Written by `arcsecond disks`. Do not edit: run `arcsecond disks add PATH`",
        "# or `arcsecond disks remove NAME` instead.",
        "# The disks of this machine Arcsecond.local can attach as Local Disk storages.",
        "services:",
    ]
    for service in DISK_SERVICES:
        lines += [f"  {service}:", "    volumes:"]
        for name, source in sorted(disks.items()):
            lines += [
                "      - type: bind",
                f"        source: {_compose_quote(source)}",
                f"        target: {DISKS_TARGET}/{name}",
            ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_disk(install, path: str, name: str = None) -> str:
    """Add a disk; answers the name it is mounted under."""
    from .local import expand_path

    source = expand_path(path.strip())
    if not Path(source).is_dir():
        raise ArcsecondError(f"{source} is not a folder of this machine.")
    disks = read_disks(install)
    for existing_name, existing_source in disks.items():
        if existing_source == source:
            return existing_name
    if name:
        name = _NAME_RE.sub("-", name.lower()).strip("-.")
        if not name:
            raise ArcsecondError("A disk name holds letters, digits, dots, dashes or underscores.")
        if name in disks:
            raise ArcsecondError(f"A disk is already mounted as {name}. `arcsecond disks list` shows them.")
    else:
        name = disk_name(source, taken=disks.keys())
    disks[name] = source
    write_disks(install, disks)
    return name


def _record_declined(install) -> None:
    from .local import _parse_env_keys

    env_path = install.env_path
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    if LOCAL_DISKS_ENV_KEY in _parse_env_keys(lines):
        return
    if lines and lines[-1].strip():
        lines.append("")
    lines += [
        "# `no`: setup and update no longer ask for disks to attach. `arcsecond disks add PATH` still does.",
        f"{LOCAL_DISKS_ENV_KEY}=no",
    ]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def offer_disks(install) -> bool:
    """The question `setup` and `update` ask once: is there a disk of this
    machine to attach? True when the disks changed."""
    if read_disks(install) or install.read_env(LOCAL_DISKS_ENV_KEY) or not sys.stdin.isatty():
        return False
    click.echo(
        "\nArcsecond.local can index data already on a disk of this machine (a \"Local Disk\" storage,"
        "\nattached in the web interface), without copying it."
    )
    if not click.confirm("Is there a disk or folder of this machine to make available?", default=False):
        _record_declined(install)
        return False
    changed = False
    while True:
        path = click.prompt("Path of the disk or folder (empty when done)", default="", show_default=False).strip()
        if not path:
            return changed
        try:
            name = add_disk(install, path)
        except ArcsecondError as e:
            click.echo(click.style(str(e), fg="red"))
            continue
        changed = True
        click.echo(click.style(f"  {path} will be available as {DISKS_TARGET}/{name}.", fg="green"))


# --- Commands ---------------------------------------------------------------


def _apply(install, restart: bool) -> None:
    if not restart:
        click.echo("Run `arcsecond restart backend worker dataworker` to make the change effective.")
        return
    from .lifecycle import _streamed

    stack.ensure_docker()
    click.echo("Recreating the services that read storages ...")
    _streamed(install, "docker compose up", "up", "-d", "--force-recreate", *DISK_SERVICES)
    click.echo(click.style("Done.", fg="green"))


_dir_option = click.option(
    "--dir",
    "directory",
    default=None,
    metavar="FOLDER",
    help="The Arcsecond.local folder (the one holding docker-compose.yml). "
    "Default: the current folder, else the one `arcsecond setup` last ran in.",
)
_no_restart_option = click.option(
    "--no-restart", is_flag=True, help="Change the configuration only; restart later."
)


@click.group(name="disks", short_help="Disks of this machine to attach as Local Disk storages.")
def disks_group():
    """The disks (or folders) of this machine Arcsecond.local can attach as
    Local Disk storages. Once added here, attach a folder of one in the web
    interface: Attached Storages, New Storage, Local Disk."""


@disks_group.command(name="list", help="List the disks made available.")
@_dir_option
@basic_options
def disks_list(directory):
    install = stack.resolve_install_dir(directory)
    disks = read_disks(install)
    if not disks:
        click.echo("No disk yet. Add one with:  arcsecond disks add PATH")
        return
    for name, source in sorted(disks.items()):
        click.echo(f"  {click.style(name, bold=True)}  {source}  (seen as {DISKS_TARGET}/{name})")


@disks_group.command(name="add", help="Make a disk or folder of this machine available.")
@click.argument("path")
@click.option("--name", default=None, help="The name it is listed under. Default: the folder's name.")
@_dir_option
@_no_restart_option
@basic_options
def disks_add(path, name, directory, no_restart):
    install = stack.resolve_install_dir(directory)
    before = read_disks(install)
    name = add_disk(install, path, name)
    if read_disks(install) == before:
        click.echo(f"{path} is already available as {name}.")
        return
    click.echo(f"{path} is available as {click.style(name, bold=True)}.")
    _apply(install, restart=not no_restart)
    click.echo("Attach a folder of it in the web interface: Attached Storages, New Storage, Local Disk.")


@disks_group.command(name="remove", help="Stop making a disk available.")
@click.argument("name")
@_dir_option
@_no_restart_option
@basic_options
def disks_remove(name, directory, no_restart):
    install = stack.resolve_install_dir(directory)
    disks = read_disks(install)
    if name not in disks:
        raise ArcsecondError(f"No disk named {name}. `arcsecond disks list` shows them.")
    del disks[name]
    write_disks(install, disks)
    click.echo(
        f"{name} removed. Local Disk storages attached from it can no longer be read; "
        "detach them in the web interface."
    )
    _apply(install, restart=not no_restart)
