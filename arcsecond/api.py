import json
import pprint
import webbrowser

import click
import requests
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

pp = pprint.PrettyPrinter(indent=4, depth=5)


class API(object):
    ENDPOINT_OBJECTS = ('/objects/', '/objects/')
    ENDPOINT_EXOPLANETS = ('/exoplanets/', '/objects/')

    ENPOINTS = [ENDPOINT_OBJECTS, ENDPOINT_EXOPLANETS]

    def __init__(self, state):
        self.state = state
        self.request_path = 'http://api.lvh.me:8000' if state.debug is True else 'https://api.arcsecond.io'
        self.open_path = 'http://localhost:8080' if state.debug is True else 'https://www.arcsecond.io'

    def get_read_url(self, endpoint, name=''):
        path = self.request_path if self.state.open is False else self.open_path
        index = 0 if open is False else 1
        url = "{}{}{}".format(path, endpoint[index], name)
        if self.state.verbose:
            click.echo('Building read URL : ' + url)
        return url

    def read(self, endpoint, name=''):
        assert (endpoint in API.ENPOINTS)
        if type(name) is tuple: name = " ".join(name)
        url = self.get_read_url(endpoint, name)

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
