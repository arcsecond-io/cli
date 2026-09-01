import click

from arcsecond.alpaca.commands import alpaca_group
from arcsecond.cloud import (
    api,
    datasets,
    login,
    me,
    telescopes,
    upload_data,
)
from arcsecond.hosting import backups, db, setup
from arcsecond.imagesources import commands as imagesources

from . import __version__
from .options import State

pass_state = click.make_pass_decorator(State, ensure=True)

VERSION_HELP_STRING = "Show the 'arcsecond' CLI version and exit."


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help=VERSION_HELP_STRING)
@click.option("-V", is_flag=True, help=VERSION_HELP_STRING)
@click.option("-h", is_flag=True, help="Show this message and exit.")
@click.pass_context
def main(ctx, version=False, v=False, h=False):
    if version or v:
        click.echo(__version__.__version__)
    elif ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command(help=VERSION_HELP_STRING)
def version():
    click.echo(__version__.__version__)


# Read/set API server to use.
main.add_command(api)

# Login to Arcsecond.
main.add_command(login)

# Read the logged-in user profile.
main.add_command(me)

# Read the list of existing datasets (for upload purposes).
main.add_command(datasets)

# Read the list of existing telescopes (for upload purposes).
main.add_command(telescopes)

# Upload a folder of files to a given dataset.
main.add_command(upload_data)

# Allow to try arcsecond by installing a local version
main.add_command(setup)

# Browse and restore Arcsecond.local DB backups.
main.add_command(backups)

# Manage the Arcsecond.local database (e.g. `arcsecond db set-password`).
main.add_command(db)

# Cameras, and the native live-image proxy that exposes them to
# Arcsecond.local Docker containers via host.docker.internal. `webcam` covers
# every camera the machine can reach, whether over USB or over the network;
# `allsky` covers all-sky cameras writing JPEGs to disk; `proxy` runs the one
# server that serves whatever those two registered.
main.add_command(imagesources.webcam)
main.add_command(imagesources.allsky)
main.add_command(imagesources.proxy)

# Removed: a network camera is a webcam. Kept only to say so — see commands.py.
main.add_command(imagesources.netcam)

# Local ASCOM Alpaca diagnostics (e.g. `arcsecond alpaca probe dome ...`).
main.add_command(alpaca_group)


# `arcsecond proxy start` launches its detached proxy as
# `python -m arcsecond.cli proxy start --foreground`, which needs this. Going
# through the interpreter rather than the console script means the background
# proxy runs on the very same Python as the command that started it.
if __name__ == "__main__":
    main()
