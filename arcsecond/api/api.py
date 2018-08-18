import json
import pprint
import webbrowser

import click
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

from arcsecond.config import config_file_path, config_file_save_api_key
from .auth import AuthAPIEndPoint
from .charts import FindingChartsAPIEndPoint
from .error import ArcsecondError
from .objects import ExoplanetsAPIEndPoint, ObjectsAPIEndPoint
from .profiles import PersonalProfileAPIEndPoint, ProfileAPIEndPoint, ProfileAPIKeyAPIEndPoint

pp = pprint.PrettyPrinter(indent=4, depth=5)


class API(object):
    ENDPOINT_OBJECTS = ObjectsAPIEndPoint.name
    ENDPOINT_EXOPLANETS = ExoplanetsAPIEndPoint.name
    ENDPOINT_FINDINGCHARTS = FindingChartsAPIEndPoint.name
    ENDPOINT_PROFILE = ProfileAPIEndPoint.name
    ENDPOINT_ME = PersonalProfileAPIEndPoint.name

    ENPOINTS = [ENDPOINT_OBJECTS,
                ENDPOINT_EXOPLANETS,
                ENDPOINT_FINDINGCHARTS,
                ENDPOINT_PROFILE,
                ENDPOINT_ME]

    _mapping = {ENDPOINT_OBJECTS: ObjectsAPIEndPoint,
                ENDPOINT_EXOPLANETS: ExoplanetsAPIEndPoint,
                ENDPOINT_FINDINGCHARTS: FindingChartsAPIEndPoint,
                ENDPOINT_PROFILE: ProfileAPIEndPoint,
                ENDPOINT_ME: PersonalProfileAPIEndPoint}

    def __init__(self, state):
        self.state = state

    def _echo_result(self, result):
        json_str = json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
        click.echo(highlight(json_str, JsonLexer(), TerminalFormatter()))

    def _echo_error(self, error):
        if self.state.debug:
            click.echo(error)
        else:
            json_obj = json.loads(error)
            click.echo(json_obj['non_field_errors'])

    def list(self, endpoint):
        if endpoint not in API.ENPOINTS:
            raise ArcsecondError("Unknown endpoint {}. Must be one of: {}".format(endpoint, ', '.join(API.ENPOINTS)))

        endpoint = API._mapping[endpoint](self.state)
        result, error = endpoint.list()
        if result:
            self._echo_result(result)
        if error:
            self._echo_error(error)

    def read(self, endpoint, name):
        if endpoint not in API.ENPOINTS:
            raise ArcsecondError("Unknown endpoint {}. Must be one of: {}".format(endpoint, ', '.join(API.ENPOINTS)))
        if not name:
            raise ArcsecondError("Invalid 'name' parameter: {}.".format(name))

        endpoint = API._mapping[endpoint](self.state)

        if type(name) is tuple:
            name = " ".join(name)

        if self.state.open:
            url = endpoint._open_url(name)
            if self.state.verbose:
                click.echo('Opening URL in browser : ' + url)
            webbrowser.open(url)
        else:
            result, error = endpoint.read(name)
            if result:
                self._echo_result(result)
            if error:
                self._echo_error(error)

    def _get_and_save_api_key(self, username, auth_token):
        headers = {'Authorization': 'Token ' + auth_token}
        result, error = ProfileAPIKeyAPIEndPoint(self.state).read(username, **headers)

        if error:
            self._echo_error(error)
            return

        if result:
            api_key = result['api_key']
            config_file_save_api_key(api_key, username, self.state.debug)
            if self.state.verbose:
                click.echo('Successfull API key retrieval and storage in {}. Enjoy.'.format(config_file_path()))

    def login(self, username, password):
        result, error = AuthAPIEndPoint(self.state).authenticate(username, password)
        if error:
            self._echo_error(error)
            return
        if result:
            self._get_and_save_api_key(username, result['key'])

    def register(self, username, email, password1, password2):
        result, error = AuthAPIEndPoint(self.state).register(username, email, password1, password2)
        if error:
            self._echo_error(error)
            return
        if result:
            self._get_and_save_api_key(username, result['key'])
