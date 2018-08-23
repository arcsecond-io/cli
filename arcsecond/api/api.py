# -*- coding: utf-8 -*-

import json
import pprint
import webbrowser

import click
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

from arcsecond.config import config_file_path, config_file_save_api_key
from arcsecond.options import State
from .auth import AuthAPIEndPoint
from .charts import FindingChartsAPIEndPoint
from .error import ArcsecondError, ArcsecondInvalidEndpointError
from .objects import ExoplanetsAPIEndPoint, ObjectsAPIEndPoint
from .profiles import PersonalProfileAPIEndPoint, ProfileAPIEndPoint, ProfileAPIKeyAPIEndPoint

pp = pprint.PrettyPrinter(indent=4, depth=5)
ECHO_PREFIX = u' • '

class ArcsecondAPI(object):
    ENDPOINT_OBJECTS = ObjectsAPIEndPoint.name
    ENDPOINT_EXOPLANETS = ExoplanetsAPIEndPoint.name
    ENDPOINT_FINDINGCHARTS = FindingChartsAPIEndPoint.name
    ENDPOINT_PROFILE = ProfileAPIEndPoint.name
    ENDPOINT_ME = PersonalProfileAPIEndPoint.name

    ENDPOINTS = [ENDPOINT_OBJECTS,
                 ENDPOINT_EXOPLANETS,
                 ENDPOINT_FINDINGCHARTS,
                 ENDPOINT_PROFILE,
                 ENDPOINT_ME]

    _mapping = {ENDPOINT_OBJECTS: ObjectsAPIEndPoint,
                ENDPOINT_EXOPLANETS: ExoplanetsAPIEndPoint,
                ENDPOINT_FINDINGCHARTS: FindingChartsAPIEndPoint,
                ENDPOINT_PROFILE: ProfileAPIEndPoint,
                ENDPOINT_ME: PersonalProfileAPIEndPoint}

    @classmethod
    def pretty_print_dict(cls, d):
        json_str = json.dumps(d, indent=4, sort_keys=True, ensure_ascii=False)
        click.echo(highlight(json_str, JsonLexer(), TerminalFormatter()))

    def __init__(self, state=None, **kwargs):
        self._is_using_cli = state is not None
        self.state = state or State()
        if 'debug' in kwargs.keys():
            self.state.debug = kwargs.get('debug')
        if 'verbose' in kwargs.keys():
            self.state.verbose = kwargs.get('verbose')

    def _echo_result(self, result):
        if not self._is_using_cli: return result
        ArcsecondAPI.pretty_print_dict(result)

    def _echo_error(self, error):
        if not self._is_using_cli: return error
        if self.state.debug:
            click.echo(error)
        else:
            json_obj = json.loads(error)
            if 'detail' in json_obj.keys():
                click.echo(ECHO_PREFIX + json_obj['detail'])
            if 'non_field_errors' in json_obj.keys():
                click.echo(ECHO_PREFIX + json_obj['non_field_errors'])

    def list(self, endpoint):
        if endpoint not in ArcsecondAPI.ENDPOINTS:
            raise ArcsecondInvalidEndpointError(endpoint, ArcsecondAPI.ENDPOINTS)

        endpoint = ArcsecondAPI._mapping[endpoint](self.state)
        result, error = endpoint.list()
        if result:
            return self._echo_result(result)
        if error:
            return self._echo_error(error)

    def read(self, endpoint, name):
        if endpoint not in ArcsecondAPI.ENDPOINTS:
            raise ArcsecondInvalidEndpointError(endpoint, ArcsecondAPI.ENDPOINTS)
        if not name:
            raise ArcsecondError("Invalid 'name' parameter: {}.".format(name))

        endpoint = ArcsecondAPI._mapping[endpoint](self.state)

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
                return self._echo_result(result)
            if error:
                return self._echo_error(error)

    def _get_and_save_api_key(self, username, auth_token):
        headers = {'Authorization': 'Token ' + auth_token}
        result, error = ProfileAPIKeyAPIEndPoint(self.state).read(username, **headers)
        if error:
            return self._echo_error(error)
        if result:
            api_key = result['api_key']
            config_file_save_api_key(api_key, username, self.state.debug)
            if self.state.verbose:
                click.echo('Successfull API key retrieval and storage in {}. Enjoy.'.format(config_file_path()))
            return self._echo_result(result)

    def login(self, username, password):
        result, error = AuthAPIEndPoint(self.state).authenticate(username, password)
        if error:
            return self._echo_error(error)
        if result:
            return self._get_and_save_api_key(username, result['key'])

    def register(self, username, email, password1, password2):
        result, error = AuthAPIEndPoint(self.state).register(username, email, password1, password2)
        if error:
            return self._echo_error(error)
        if result:
            return self._get_and_save_api_key(username, result['key'])
