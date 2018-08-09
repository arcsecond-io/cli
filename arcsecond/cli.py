import click

from .api import API
from .options import AliasedGroup, State, common_options

__version__ = '0.2.0'

pass_state = click.make_pass_decorator(State, ensure=True)


@click.group(cls=AliasedGroup, invoke_without_command=True)
@click.option('-v', '--version', is_flag=True)
@click.pass_context
def main(ctx, version=False):
    if ctx.invoked_subcommand is None and version:
        click.echo(__version__)


@main.command(help='Request single object information (in the /objects/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@common_options
@pass_state
def object(state, name):
    API(state).read(API.ENDPOINT_OBJECTS, name)


@main.command(help='Request single exoplanet information (in the /exoplanets/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@common_options
@pass_state
def exoplanet(state, name):
    API(state).read(API.ENDPOINT_EXOPLANETS, name)


# @main.command()
# @click.option('--username', required=True, nargs=1, prompt=True)
# @click.option('--password', required=True, nargs=1, prompt=True, hide_input=True)
# @common_options
# @pass_state
# def login(state, username, password):
#     API(state).login(username, password)
