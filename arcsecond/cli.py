import click

from .api import API
from .options import AliasedGroup, State, basic_options, open_options

__version__ = '0.2.0'

pass_state = click.make_pass_decorator(State, ensure=True)


@click.group(cls=AliasedGroup, invoke_without_command=True)
@click.option('-v', '--version', is_flag=True, help="Show the CLI version and exit.")
@click.pass_context
def main(ctx, version=False):
    if ctx.invoked_subcommand is None and version:
        click.echo(__version__)


@main.command(help='Request object(s) information (in the /objects/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def objects(state, name):
    API(state).read(API.ENDPOINT_OBJECTS, name)


@main.command(help='Request exoplanet(s) information (in the /exoplanets/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def exoplanets(state, name):
    API(state).read(API.ENDPOINT_EXOPLANETS, name)


@main.command(help='Request object(s) finding charts (in the /findingcharts/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def charts(state, name):
    API(state).read(API.ENDPOINT_FINDINGCHARTS, name)


@main.command(help='Login to your personnal Arcsecond.io account, and retrieve the API key.')
@click.option('--username', required=True, nargs=1, prompt=True)
@click.option('--password', required=True, nargs=1, prompt=True, hide_input=True)
@basic_options
@pass_state
def login(state, username, password):
    API(state).login(username, password)
