"""`arcsecond start`, `stop`, `restart`, `status`, `logs`, `update`.

The operator's side of an Arcsecond.local installation, without a `docker`
command in sight. Each command finds the installation the same way (see
stack.resolve_install_dir), checks Docker is reachable, and turns compose's
failures into sentences.
"""

import subprocess

import click

from arcsecond.api.config import ArcsecondConfig
from arcsecond.errors import ArcsecondError
from arcsecond.options import basic_options

from . import stack
from .local import (
    LOCAL_API_NAME,
    _record_optional_service_decision,
    _resolve_optional_services,
    template_versions,
    write_docker_compose_file,
    write_env_file,
)

dir_option = click.option(
    "--dir",
    "directory",
    default=None,
    metavar="FOLDER",
    help="The Arcsecond.local folder (the one holding docker-compose.yml). "
    "Default: the current folder, else the one `arcsecond setup` last ran in.",
)


def _echo_progress(line: str) -> None:
    # Compose's own progress lines, dimmed so the CLI's sentences stand out.
    click.echo(click.style(f"  {line}", dim=True), err=True)


def _streamed(install, what: str, *args: str) -> None:
    result = stack.compose_streaming(install, *args, echo=_echo_progress)
    if result.returncode != 0:
        stack.raise_compose_failure(what, result)


def _print_addresses(install) -> None:
    addresses = stack.frontend_addresses(install)
    click.echo("\nArcsecond.local is at:")
    for address in addresses:
        click.echo("  " + click.style(address, fg="cyan", bold=True))
    if len(addresses) == 1:
        click.echo(
            "\n  That address only works on this machine. To let other computers "
            "in, see\n  https://docs.arcsecond.io/local/lan-access"
        )


def _hint_api_pointer() -> None:
    if ArcsecondConfig.current_api_name() == LOCAL_API_NAME:
        return
    if LOCAL_API_NAME not in ArcsecondConfig.registered_api_names():
        return
    click.echo(
        "\nTo use this CLI against this installation (uploads, scripts):\n"
        f"  arcsecond api use {LOCAL_API_NAME}"
    )


def _wait_and_report(install) -> None:
    click.echo("\nWaiting for the backend to be ready", nl=False)
    reason = stack.wait_for_backend(tick=lambda: click.echo(".", nl=False))
    click.echo("")
    if reason is None:
        click.echo(click.style("Arcsecond.local is up.", fg="green", bold=True))
        return
    if reason == "missing":
        raise ArcsecondError(
            f"The {stack.API_CONTAINER} container is not there. `arcsecond status` "
            "shows what compose knows of; `arcsecond logs backend` shows why."
        )
    if reason == "unhealthy":
        raise ArcsecondError(
            "The backend started but reports itself unhealthy.\n"
            "See what it says:  arcsecond logs backend --tail 100"
        )
    raise ArcsecondError(
        f"The backend did not become ready within {stack.BACKEND_WAIT_TIMEOUT:.0f}s.\n"
        "The first start loads a lot of data and can take longer on a slow "
        "machine — it may simply still be working. Check with:\n"
        "  arcsecond status\n"
        "  arcsecond logs backend --tail 100"
    )


@click.command(help="Start Arcsecond.local.")
@dir_option
@click.option("--pull", is_flag=True, help="Download newer images first.")
@click.option(
    "--recreate",
    is_flag=True,
    help="Recreate every container, so that changes to .env are picked up.",
)
@click.option(
    "--no-wait",
    is_flag=True,
    help="Return as soon as the containers are started, without waiting for "
    "the backend to be ready.",
)
@basic_options
def start(directory, pull, recreate, no_wait):
    """Start Arcsecond.local, or bring a running one in line with its files.

    Safe to run again at any time: containers already running and up to date
    are left alone. The first start downloads the Docker images, which takes
    a while.
    """
    install = stack.resolve_install_dir(directory)
    stack.ensure_docker()

    click.echo(f"Starting Arcsecond.local from {install.path} ...")
    if pull:
        _streamed(install, "docker compose pull", "pull")
    args = ["up", "-d"] + (["--force-recreate"] if recreate else [])
    _streamed(install, "docker compose up", *args)

    if not no_wait:
        _wait_and_report(install)
    _print_addresses(install)
    _hint_api_pointer()


@click.command(help="Stop Arcsecond.local.")
@dir_option
@click.option(
    "--down",
    is_flag=True,
    help="Also remove the stopped containers and the network. Your data "
    "(database, files) is never touched.",
)
@basic_options
def stop(directory, down):
    """Stop the containers. `arcsecond start` brings them back.

    A stopped installation stays stopped across a reboot; one that was running
    comes back on its own when Docker does.
    """
    install = stack.resolve_install_dir(directory)
    stack.ensure_docker()
    click.echo(f"Stopping Arcsecond.local in {install.path} ...")
    if down:
        _streamed(install, "docker compose down", "down")
    else:
        _streamed(install, "docker compose stop", "stop")
    click.echo(click.style("Arcsecond.local is stopped.", fg="green"))


@click.command(help="Recreate containers so they pick up a changed .env.")
@dir_option
@click.argument("services", nargs=-1)
@basic_options
def restart(directory, services):
    """Recreate the given services — or all of them — from their current
    configuration.

    This is what to run after editing .env: a plain stop/start would keep the
    old values. Naming services limits it: `arcsecond restart backend worker`.
    """
    install = stack.resolve_install_dir(directory)
    stack.ensure_docker()
    which = ", ".join(services) if services else "every service"
    click.echo(f"Recreating {which} ...")
    _streamed(install, "docker compose up", "up", "-d", "--force-recreate", *services)
    if not services or "backend" in services:
        _wait_and_report(install)
    else:
        click.echo(click.style("Done.", fg="green"))


def _state_style(state: str, health):
    state = (state or "").lower()
    if state == "running":
        if health in (None, "healthy"):
            return click.style(state, fg="green")
        return click.style(f"{state} ({health})", fg="yellow")
    if state in ("exited", "dead"):
        return click.style(state, fg="red")
    return click.style(state or "?", fg="yellow")


def _print_services_table(rows) -> None:
    if not rows:
        click.echo(
            "  No container exists yet: the installation has never been started."
        )
        return
    width = max(len(r[0]) for r in rows)
    for service, state, image in rows:
        click.echo(f"  {service.ljust(width)}  {state}  {click.style(image, dim=True)}")


@click.command(help="Say what is running, and whether it is up to date.")
@dir_option
@basic_options
def status(directory):
    install = stack.resolve_install_dir(directory)
    click.echo(f"Installation: {install.path}")

    current, packaged = template_versions(install)
    if current == packaged:
        click.echo(f"Compose file:  version {current} (current)")
    else:
        click.echo(
            f"Compose file:  version {current or '?'} — the CLI ships {packaged}. "
            "Run `arcsecond update`."
        )

    try:
        compose_version = stack.ensure_docker()
    except ArcsecondError as e:
        click.echo(f"Docker:        {click.style('unavailable', fg='red')}")
        click.echo("  " + str(e).replace("\n", "\n  "))
        return
    click.echo(f"Docker:        compose {compose_version}")

    click.echo("\nContainers:")
    rows = []
    for item in stack.services_status(install):
        service = item.get("Service") or item.get("Name") or "?"
        health = (item.get("Health") or "").lower() or None
        rows.append(
            (
                service,
                _state_style(item.get("State", ""), health),
                item.get("Image", ""),
            )
        )
    _print_services_table(sorted(rows, key=lambda r: r[0]))

    from arcsecond.imagesources import commands as cameras

    port = cameras._running_proxy_port()
    if port is None:
        click.echo("\nLive-image proxy: not running")
    else:
        click.echo(f"\nLive-image proxy: running on port {port}")
    try:
        from arcsecond.imagesources import autostart

        if autostart.is_enabled():
            click.echo("  It starts again when you log in.")
    except Exception:  # noqa: BLE001 — a status line, never a failure
        pass

    if rows:
        _print_addresses(install)


@click.command(help="Show the logs of Arcsecond.local, or of one service.")
@dir_option
@click.argument("service", required=False)
@click.option("-f", "--follow", is_flag=True, help="Keep printing as new lines arrive.")
@click.option(
    "--tail",
    default="200",
    show_default=True,
    help="How many recent lines to show ('all' for everything).",
)
@basic_options
def logs(directory, service, follow, tail):
    """Show recent logs. Services are named as in `arcsecond status`:
    backend, worker, beat, web, db, broker, platesolver, alerts."""
    install = stack.resolve_install_dir(directory)
    stack.ensure_docker()
    args = ["logs", "--tail", str(tail)]
    if follow:
        args.append("--follow")
    if service:
        args.append(service)
    try:
        result = subprocess.run(
            stack.compose_command(install, *args), cwd=str(install.path), check=False
        )
    except KeyboardInterrupt:
        click.echo("")
        return
    if result.returncode != 0:
        raise ArcsecondError(
            "`docker compose logs` failed. Is the service name right? "
            "`arcsecond status` lists them."
        )


@click.command(help="Update Arcsecond.local to the latest images.")
@dir_option
@basic_options
def update(directory):
    """Bring the installation up to date: refresh docker-compose.yml from this
    CLI, download the latest images, and restart what changed.

    Update the CLI itself first, so that the compose file it writes is the
    newest one:  pip install --upgrade arcsecond
    """
    install = stack.resolve_install_dir(directory)
    stack.ensure_docker()

    click.echo(f"Updating Arcsecond.local in {install.path} ...\n")
    click.echo("Refreshing the configuration files:")
    enabled, removed, to_record = _resolve_optional_services(install.env_path, {})
    write_env_file(directory=install.path)
    for name, answer in to_record:
        _record_optional_service_decision(install.env_path, name, answer)
    write_docker_compose_file(
        enabled_services=enabled, removed_services=removed, directory=install.path
    )

    click.echo("\nDownloading the latest images:")
    _streamed(install, "docker compose pull", "pull")
    click.echo("\nRestarting what changed:")
    _streamed(install, "docker compose up", "up", "-d")
    _wait_and_report(install)
    _print_addresses(install)


__all__ = ["start", "stop", "restart", "status", "logs", "update"]
