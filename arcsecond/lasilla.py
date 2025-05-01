import click

from . import __version__
from .hosting import run_arcsecond, stop_arcsecond, print_arcsecond_status
from .options import State, basic_options

pass_state = click.make_pass_decorator(State, ensure=True)

VERSION_HELP_STRING = "Show the 'lasilla' CLI version and exit."


######################## SELF-HOSTING ##################################################################################

@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help=VERSION_HELP_STRING)
@click.option('-V', is_flag=True, help=VERSION_HELP_STRING)
@click.option('-h', is_flag=True, help="Show this message and exit.")
@click.pass_context
def main(ctx, version=False, v=False, h=False):
    if version or v:
        click.echo(__version__.__version__)
    elif ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command(name='try', help='Try a full-featured demo of a self-hosted Arcsecond instance.')
@click.option('-s', '--skip-setup', required=False, is_flag=True, help="Skip the setup.")
@basic_options
@pass_state
def do_try(state, skip_setup=False):
    run_arcsecond(state, do_try=True, skip_setup=skip_setup)


# @main.command(name='install', help='Install a true self-hosting Arcsecond instance.')
# @click.option('-s', '--skip-setup', required=False, is_flag=True, help="Skip the setup.")
# @basic_options
# @pass_state
# def do_install(state, skip_setup=False):
#     run_arcsecond(state, do_try=False, skip_setup=skip_setup)


@main.command(name='stop', help='Stop the running self-hosted Arcsecond instance.')
@pass_state
def do_stop(state):
    stop_arcsecond()


@main.command(name='status', help='Stop the running self-hosted Arcsecond instance.')
@pass_state
def do_get_status(state):
    print_arcsecond_status()
