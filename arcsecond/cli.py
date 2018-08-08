import json
import pprint
import webbrowser

import click
import requests
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

from .options import AliasedGroup, State, common_options

__version__ = '0.2.0'

pp = pprint.PrettyPrinter(indent=4, depth=5)
pass_state = click.make_pass_decorator(State, ensure=True)


class API(object):
    ENDPOINT_OBJECTS = ('/objects/', '/objects/')
    ENDPOINT_EXOPLANETS = ('/exoplanets/', '/objects/')

    ENPOINTS = [ENDPOINT_OBJECTS, ENDPOINT_EXOPLANETS]

    def __init__(self, state, endpoint):
        assert (endpoint in API.ENPOINTS)
        self.state = state
        self.endpoint = endpoint
        self.request_path = 'http://api.lvh.me:8000' if state.debug is True else 'https://api.arcsecond.io'
        self.open_path = 'http://localhost:8080' if state.debug is True else 'https://www.arcsecond.io'

    def get_read_url(self, name=''):
        path = self.request_path if self.state.open is False else self.open_path
        index = 0 if open is False else 1
        return "{}{}{}".format(path, self.endpoint[index], name)

    def read(self, name=''):
        if type(name) is tuple: name = " ".join(name)
        url = self.get_read_url(name)

        if self.state.open:
            if self.state.verbose:
                click.echo('Opening URL in browser : ' + url)
            webbrowser.open(url)
        else:
            if self.state.verbose:
                click.echo('Requesting URL ' + url + ' ...')
            r = requests.get(url)
            if r.status_code == 200:
                json_str = json.dumps(r.json(), indent=4, sort_keys=True)
                click.echo(highlight(json_str, JsonLexer(), TerminalFormatter()))
            else:
                json_obj = json.loads(r.text)
                click.echo(json_obj['detail'])

    def login(self, username, password):
        r = requests.post(self.request_path + '/auth/login/', data={'username': username, 'password': password})
        if r.status_code == 200:
            json_str = json.dumps(r.json(), indent=4, sort_keys=True)
            click.echo(highlight(json_str, JsonLexer(), TerminalFormatter()))
        else:
            json_obj = json.loads(r.text)
            click.echo(json_obj['non_field_errors'])


@click.group(cls=AliasedGroup, invoke_without_command=True)
@click.option('-v', '--version', is_flag=True)
@click.pass_context
def main(ctx, version=False):
    if ctx.invoked_subcommand is None and version:
        click.echo(__version__)


@main.command()
@click.argument('name', required=True, nargs=-1)
@common_options
@pass_state
def object(state, name):
    API(state, API.ENDPOINT_OBJECTS).read(name)


@main.command()
@click.argument('name', required=True, nargs=-1)
@common_options
@pass_state
def exoplanet(state, name):
    API(state, API.ENDPOINT_EXOPLANETS).read(name)


@main.command()
@click.option('--username', required=True, nargs=1, prompt=True)
@click.option('--password', required=True, nargs=1, prompt=True, hide_input=True)
@common_options
@pass_state
def login(state, username, password):
    url = 'http://api.lvh.me:8000' if state.debug is True else 'https://api.arcsecond.io'
    r = requests.post(url + '/auth/login/', data={'username': username, 'password': password})
    if r.status_code == 200:
        json_str = json.dumps(r.json(), indent=4, sort_keys=True)
        click.echo(highlight(json_str, JsonLexer(), TerminalFormatter()))
    else:
        json_obj = json.loads(r.text)
        click.echo(json_obj)
