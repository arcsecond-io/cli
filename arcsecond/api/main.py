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
from .activities import ActivitiesAPIEndPoint
from .auth import AuthAPIEndPoint
from .charts import FindingChartsAPIEndPoint
from .error import ArcsecondInvalidEndpointError
from .objects import ExoplanetsAPIEndPoint, ObjectsAPIEndPoint
from .observingruns import NightLogAPIEndPoint, ObservingRunsAPIEndPoint
from .observingsites import InstrumentsAPIEndPoint, ObservingSitesAPIEndPoint, TelescopesAPIEndPoint
from .profiles import PersonalProfileAPIEndPoint, ProfileAPIEndPoint, ProfileAPIKeyAPIEndPoint

pp = pprint.PrettyPrinter(indent=4, depth=5)
ECHO_PREFIX = u' • '

__all__ = ["ArcsecondAPI"]

ENDPOINTS = [ActivitiesAPIEndPoint,
             FindingChartsAPIEndPoint,
             ObjectsAPIEndPoint,
             ExoplanetsAPIEndPoint,
             ProfileAPIEndPoint,
             PersonalProfileAPIEndPoint,
             ObservingSitesAPIEndPoint,
             TelescopesAPIEndPoint,
             InstrumentsAPIEndPoint,
             ObservingRunsAPIEndPoint,
             NightLogAPIEndPoint]


def set_endpoints_property(cls):
    for endpoint_class in ENDPOINTS:
        setattr(cls, 'ENDPOINT_' + endpoint_class.name.upper(), endpoint_class)
    return cls


@set_endpoints_property
class ArcsecondAPI(object):

    @classmethod
    def pretty_print_dict(cls, d):
        json_str = json.dumps(d, indent=4, sort_keys=True, ensure_ascii=False)
        click.echo(highlight(json_str, JsonLexer(), TerminalFormatter()).strip())  # .strip() avoids the empty newline

    def __init__(self, endpoint=None, state=None, **kwargs):
        self._endpoint = self._check_endpoint(endpoint)
        self._is_using_cli = state is not None and isinstance(state, State)  # State class is not exposed inside module.
        self.state = state or State()
        if 'debug' in kwargs.keys():
            self.state.debug = kwargs.get('debug')
        if 'verbose' in kwargs.keys():
            self.state.verbose = kwargs.get('verbose')

    def _echo_result(self, result):
        if not self._is_using_cli:
            return result  # Making sure to return json as it is for module usage.
        ArcsecondAPI.pretty_print_dict(result)

    def _echo_error(self, error):
        if not self._is_using_cli:
            return error

        if self.state.debug:
            click.echo(error)
        else:
            json_obj = json.loads(error)
            if 'detail' in json_obj.keys():
                click.echo(ECHO_PREFIX + json_obj['detail'])
            if 'non_field_errors' in json_obj.keys():
                click.echo(ECHO_PREFIX + json_obj['non_field_errors'])

    def _echo_response(self, response):
        result, error = response
        if result is not None:  # check against None, to avoid skipping empty lists.
            return self._echo_result(result)
        if error is not None:
            return self._echo_error(error)

    def _check_endpoint(self, endpoint):
        if endpoint is not None and endpoint not in ENDPOINTS:
            raise ArcsecondInvalidEndpointError(endpoint, ENDPOINTS)
        return endpoint

    def list(self, name=None):
        return self._echo_response(self._endpoint(self.state).list(name))

    def create(self, payload):
        return self._echo_response(self._endpoint(self.state).create(payload))

    def read(self, id_name_uuid):
        if not id_name_uuid:
            self.list()
            return

        if type(id_name_uuid) is tuple:
            id_name_uuid = " ".join(id_name_uuid)

        if self.state.open:
            url = self._endpoint(self.state)._open_url(id_name_uuid)
            if self.state.verbose:
                click.echo('Opening URL in browser : ' + url)
            webbrowser.open(url)
        else:
            return self._echo_response(self._endpoint(self.state).read(id_name_uuid))

    def update(self, id_name_uuid, payload):
        return self._echo_response(self._endpoint(self.state).update(id_name_uuid, payload))

    def delete(self, id_name_uuid):
        return self._echo_response(self._endpoint(self.state).delete(id_name_uuid))

    def _get_and_save_api_key(self, username, auth_token):
        headers = {'Authorization': 'Token ' + auth_token}
        result, error = ProfileAPIKeyAPIEndPoint(self.state).read(username, **headers)
        if error is not None:
            return self._echo_error(error)
        if result is not None:
            api_key = result['api_key']
            config_file_save_api_key(api_key, username, self.state.debug)
            if self.state.verbose:
                click.echo('Successfull API key retrieval and storage in {}. Enjoy.'.format(config_file_path()))
            return self._echo_result(result)

    def login(self, username, password):
        result, error = AuthAPIEndPoint(self.state).authenticate(username, password)
        if error is not None:
            return self._echo_error(error)
        if result is not None:
            return self._get_and_save_api_key(username, result['key'])

    def register(self, username, email, password1, password2):
        result, error = AuthAPIEndPoint(self.state).register(username, email, password1, password2)
        if error is not None:
            return self._echo_error(error)
        if result is not None:
            return self._get_and_save_api_key(username, result['key'])
