import click

from arcsecond.cloud import (
    allskycameras,
    api,
    datasets,
    login,
    me,
    telescopes,
    upload_data,
)
from arcsecond.hosting import setup

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

# Read the list of existing allskycameras (for upload purposes).
main.add_command(allskycameras)

# Upload a folder of files to a given dataset.
main.add_command(upload_data)

# Allow to try arcsecond by installing a local version
main.add_command(setup)
