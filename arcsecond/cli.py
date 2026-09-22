import click

from arcsecond.alpaca.commands import alpaca_group
from arcsecond.cloud import (
    api,
    datasets,
    login,
    telescopes,
    upload,
    upload_data,
)
from arcsecond.docgen import docs
from arcsecond.hosting import (
    backups,
    check_cmd,
    db,
    logs,
    restart,
    setup,
    start,
    status,
    stop,
    update,
)
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


# Which API server every command talks to (`arcsecond api use <name>`).
main.add_command(api)

# Login to that server.
main.add_command(login)

# Read the list of existing datasets / telescopes (for upload purposes).
main.add_command(datasets)
main.add_command(telescopes)

# Upload a folder of files to a given dataset. `upload-data` is the pre-4.0
# name, kept hidden so existing scripts keep working.
main.add_command(upload)
main.add_command(upload_data)

# Arcsecond.local: write the installation, then run it — no `docker` to type.
main.add_command(setup)
main.add_command(start)
main.add_command(stop)
main.add_command(restart)
main.add_command(status)
main.add_command(logs)
main.add_command(update)

# Is it reachable from the rest of the observatory, and if not, why not.
main.add_command(check_cmd)

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

# Local ASCOM Alpaca diagnostics (e.g. `arcsecond alpaca probe dome ...`).
main.add_command(alpaca_group)

# The tool describing itself: `arcsecond docs commands --out DIR` writes the
# command reference the documentation site publishes. Hidden — it is for the
# documentation build, not for operators.
main.add_command(docs)


# `arcsecond proxy start` launches its detached proxy as
# `python -m arcsecond.cli proxy start --foreground`, which needs this. Going
# through the interpreter rather than the console script means the background
# proxy runs on the very same Python as the command that started it.
if __name__ == "__main__":
    main()
