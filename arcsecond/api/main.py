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
from .error import ArcsecondInvalidEndpointError
from .endpoints import (ActivitiesAPIEndPoint,
                        FindingChartsAPIEndPoint,
                        ObjectsAPIEndPoint,
                        ExoplanetsAPIEndPoint,
                        ProfileAPIEndPoint,
                        PersonalProfileAPIEndPoint,
                        ProfileAPIKeyAPIEndPoint,
                        ObservingSitesAPIEndPoint,
                        TelescopesAPIEndPoint,
                        InstrumentsAPIEndPoint,
                        ObservingRunsAPIEndPoint,
                        NightLogAPIEndPoint,
                        DatasetsAPIEndPoint,
                        FITSFilesAPIEndPoint,
                        SatellitesAPIEndPoint)

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
             NightLogAPIEndPoint,
             DatasetsAPIEndPoint,
             FITSFilesAPIEndPoint,
             SatellitesAPIEndPoint]


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
        self.state = state or State(is_using_cli=False)
        if 'debug' in kwargs.keys():
            self.state.debug = kwargs.get('debug')
        if 'verbose' in kwargs.keys():
            self.state.verbose = kwargs.get('verbose')
        endpoint_class = self._check_endpoint_class(endpoint)  # this an endpoint *class*
        self.endpoint = endpoint_class(self.state, prefix=kwargs.get('prefix', '')) if endpoint_class else None

    @classmethod
    def _echo_result(cls, state, result):
        if not state.is_using_cli:
            return result  # Making sure to return json as it is for module usage.
        ArcsecondAPI.pretty_print_dict(result)

    @classmethod
    def _echo_error(cls, state, error):
        if not state.is_using_cli:
            return error

        if state and state.debug:
            click.echo(error)
        else:
            json_obj = json.loads(error)
            if 'detail' in json_obj.keys():
                click.echo(ECHO_PREFIX + json_obj['detail'])
            if 'non_field_errors' in json_obj.keys():
                errors = json_obj['non_field_errors']
                message = ', '.join(errors) if isinstance(error, list) else str(errors)
                click.echo(ECHO_PREFIX + message)

    def _echo_request_result(self, result):
        ArcsecondAPI._echo_result(self.state, result)

    def _echo_request_error(self, error):
        ArcsecondAPI._echo_error(self.state, error)

    def _echo_response(self, response):
        result, error = response
        if result is not None:  # check against None, to avoid skipping empty lists.
            return self._echo_request_result(result)
        if error is not None:
            return self._echo_request_error(error)

    def _check_endpoint_class(self, endpoint):
        if endpoint is not None and endpoint not in ENDPOINTS:
            raise ArcsecondInvalidEndpointError(endpoint, ENDPOINTS)
        return endpoint

    def list(self, name=None, **headers):
        return self._echo_response(self.endpoint.list(name, **headers))

    def create(self, payload, **headers):
        return self._echo_response(self.endpoint.create(payload, **headers))

    def read(self, id_name_uuid, **headers):
        if not id_name_uuid:
            self.list()
            return

        if type(id_name_uuid) is tuple:
            id_name_uuid = " ".join(id_name_uuid)

        if self.state.open:
            url = self.endpoint._open_url(id_name_uuid)
            if self.state.verbose:
                click.echo('Opening URL in browser : ' + url)
            webbrowser.open(url)
        else:
            return self._echo_response(self.endpoint.read(id_name_uuid, **headers))

    def update(self, id_name_uuid, payload, **headers):
        return self._echo_response(self.endpoint.update(id_name_uuid, payload, **headers))

    def delete(self, id_name_uuid, **headers):
        return self._echo_response(self.endpoint.delete(id_name_uuid, **headers))

    @classmethod
    def _get_and_save_api_key(cls, state, username, auth_token):
        headers = {'Authorization': 'Token ' + auth_token}
        result, error = ProfileAPIKeyAPIEndPoint(state).read(username, **headers)
        if error:
            return ArcsecondAPI._echo_error(state, error)
        if result:
            api_key = result['api_key']
            config_file_save_api_key(api_key, username, state.debug)
            if state.verbose:
                click.echo('Successfull API key retrieval and storage in {}. Enjoy.'.format(config_file_path()))
            return ArcsecondAPI._echo_result(state, result)

    @classmethod
    def login(cls, username, password, state=None):
        state = state or State()
        result, error = AuthAPIEndPoint(state).login(username, password)
        if error:
            return ArcsecondAPI._echo_error(state, error)
        if result:
            return ArcsecondAPI._get_and_save_api_key(state, username, result['key'])

    @classmethod
    def register(cls, username, email, password1, password2, state=None):
        state = state or State()
        result, error = AuthAPIEndPoint(state).register(username, email, password1, password2)
        if error:
            return ArcsecondAPI._echo_request_error(state, error)
        if result:
            return ArcsecondAPI._get_and_save_api_key(state, username, result['key'])
