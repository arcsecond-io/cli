import json
import pprint
import webbrowser

import click
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

from arcsecond.config import config_file_save_api_key, config_file_path

from .auth import AuthAPIEndPoint, APIKeyAPIEndPoint
from .charts import FindingChartsAPIEndPoint
from .objects import ObjectsAPIEndPoint, ExoplanetsAPIEndPoint

pp = pprint.PrettyPrinter(indent=4, depth=5)


class API(object):
    ENDPOINT_OBJECTS = ObjectsAPIEndPoint.name
    ENDPOINT_EXOPLANETS = ExoplanetsAPIEndPoint.name
    ENDPOINT_FINDINGCHARTS = FindingChartsAPIEndPoint.name

    ENPOINTS = [ENDPOINT_OBJECTS, ENDPOINT_EXOPLANETS, ENDPOINT_FINDINGCHARTS]

    _mapping = {ENDPOINT_OBJECTS: ObjectsAPIEndPoint,
                ENDPOINT_EXOPLANETS: ExoplanetsAPIEndPoint,
                ENDPOINT_FINDINGCHARTS: FindingChartsAPIEndPoint}


    def __init__(self, state):
        self.state = state


    def list(self, endpoint):
        assert (endpoint in API.ENPOINTS)
        endpoint = API._mapping[endpoint](self.state)
        result = endpoint.list()
        if result:
            json_str = json.dumps(result, indent=4, sort_keys=True)
            click.echo(highlight(json_str, JsonLexer(), TerminalFormatter()))


    def read(self, endpoint, name):
        assert (endpoint in API.ENPOINTS)
        endpoint = API._mapping[endpoint](self.state)

        if type(name) is tuple:
            name = " ".join(name)

        if self.state.open:
            url = endpoint._open_url(name)
            if self.state.verbose:
                click.echo('Opening URL in browser : ' + url)
            webbrowser.open(url)
        else:
            result = endpoint.read(name)
            if result:
                json_str = json.dumps(result, indent=4, sort_keys=True)
                click.echo(highlight(json_str, JsonLexer(), TerminalFormatter()))


    def login(self, username, password):
        result = AuthAPIEndPoint(self.state).authenticate(username, password)
        if result:
            auth_token = result['key']
            headers = {'Authorization': 'Token ' + auth_token}
            result = APIKeyAPIEndPoint(self.state).read(username, **headers)
            if result:
                api_key = result['api_key']
                config_file_save_api_key(api_key)
                if self.state.verbose:
                    click.echo('Successfull API key retrieval and storage in {}. Enjoy.'.format(config_file_path()))
