# -*- coding: utf-8 -*-

import json
import os
import pprint
import webbrowser

import click
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

from arcsecond.config import \
    (config_file_path,
     config_file_save_api_key,
     config_file_save_membership_role,
     config_file_read_api_key)

from arcsecond.options import State
from .auth import AuthAPIEndPoint
from .endpoints import (ActivitiesAPIEndPoint,
                        DatasetsAPIEndPoint,
                        ExoplanetsAPIEndPoint,
                        FITSFilesAPIEndPoint,
                        FindingChartsAPIEndPoint,
                        InstrumentsAPIEndPoint,
                        NightLogAPIEndPoint,
                        ObjectsAPIEndPoint,
                        ObservingRunsAPIEndPoint,
                        ObservingSitesAPIEndPoint,
                        PersonalProfileAPIEndPoint,
                        ProfileAPIEndPoint,
                        ProfileAPIKeyAPIEndPoint,
                        SatellitesAPIEndPoint,
                        TelescopesAPIEndPoint,
                        TelegramsATelAPIEndPoint)

from .error import ArcsecondInvalidEndpointError, ArcsecondTooManyPrefixesError, ArcsecondNotLoggedInError
from .helpers import make_file_upload_payload

pp = pprint.PrettyPrinter(indent=4, depth=5)
ECHO_PREFIX = u' • '

__all__ = ["ArcsecondAPI"]

ENDPOINTS = [ActivitiesAPIEndPoint,
             DatasetsAPIEndPoint,
             ExoplanetsAPIEndPoint,
             FITSFilesAPIEndPoint,
             FindingChartsAPIEndPoint,
             InstrumentsAPIEndPoint,
             NightLogAPIEndPoint,
             ObjectsAPIEndPoint,
             ObservingRunsAPIEndPoint,
             ObservingSitesAPIEndPoint,
             PersonalProfileAPIEndPoint,
             ProfileAPIEndPoint,  # And not ProfileAPIKeyAPIEndPoint...
             SatellitesAPIEndPoint,
             TelescopesAPIEndPoint,
             TelegramsATelAPIEndPoint]

# Tricky but values must NOT have leading slash, but MUST have trailing one...
VALID_PREFIXES = {'dataset': 'datasets/'}


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

    def __init__(self, endpoint_class=None, state=None, **kwargs):
        if not self.__class__.is_logged_in(state):
            raise ArcsecondNotLoggedInError()

        self.state = state or State(is_using_cli=False)
        if 'debug' in kwargs.keys():
            self.state.debug = kwargs.get('debug')
        if 'verbose' in kwargs.keys():
            self.state.verbose = kwargs.get('verbose')

        prefix = kwargs.get('prefix', '')
        possible_prefixes = set(kwargs.keys()).intersection(VALID_PREFIXES.keys())
        if len(possible_prefixes) > 1:
            raise ArcsecondTooManyPrefixesError(possible_prefixes)
        elif len(possible_prefixes) == 1 and prefix:
            raise ArcsecondTooManyPrefixesError([possible_prefixes.pop(), prefix])
        elif len(possible_prefixes) == 1 and not prefix:
            prefix_key = possible_prefixes.pop()
            prefix = VALID_PREFIXES[prefix_key] + kwargs[prefix_key]

        endpoint_class = self._check_endpoint_class(endpoint_class)
        self.endpoint = endpoint_class(self.state, prefix=prefix) if endpoint_class else None

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
            elif 'error' in json_obj.keys():
                click.echo(ECHO_PREFIX + json_obj['error'])
            elif 'non_field_errors' in json_obj.keys():
                errors = json_obj['non_field_errors']
                message = ', '.join(errors) if isinstance(error, list) else str(errors)
                click.echo(ECHO_PREFIX + message)
            else:
                click.echo(ECHO_PREFIX + str(error))

    def _echo_request_result(self, result):
        return ArcsecondAPI._echo_result(self.state, result)

    def _echo_request_error(self, error):
        return ArcsecondAPI._echo_error(self.state, error)

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

    def _check_for_file_in_payload(self, payload):
        if isinstance(payload, str) and os.path.exists(payload) and os.path.isfile(payload):
            return make_file_upload_payload(payload)  # transform a str into a dict
        elif isinstance(payload, dict) and 'file' in payload.keys():
            file_value = payload.pop('file')  # .pop() not .get()
            if file_value and os.path.exists(file_value) and os.path.isfile(file_value):
                payload.update(**make_file_upload_payload(file_value))  # unpack the resulting dict of make_file...()
            else:
                payload.update(file=file_value)  # do nothing, it's not a file...
        return payload

    def list(self, name=None, **headers):
        return self._echo_response(self.endpoint.list(name, **headers))

    def create(self, payload, **headers):
        payload = self._check_for_file_in_payload(payload)
        return self._echo_response(self.endpoint.create(payload, **headers))

    def read(self, id_name_uuid, **headers):
        if not id_name_uuid:
            return self.list()

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
        payload = self._check_for_file_in_payload(payload)
        return self._echo_response(self.endpoint.update(id_name_uuid, payload, **headers))

    def delete(self, id_name_uuid, **headers):
        return self._echo_response(self.endpoint.delete(id_name_uuid, **headers))

    @classmethod
    def _check_organisation_membership(cls, state, username, subdomain):
        if state.verbose:
            click.echo('Checking Membership of Organisation with subdomain "{}"...'.format(subdomain))
        profile, error = PersonalProfileAPIEndPoint(State(verbose=False, debug=state.debug)).read(username)
        if error:
            ArcsecondAPI._echo_error(state, error)
        else:
            memberships = {m['organisation']['subdomain']: m['role'] for m in profile['memberships']}
            if subdomain in memberships.keys():
                if state.verbose:
                    click.echo('Membership confirmed. Role is "{}", stored in {}.'
                               .format(memberships[subdomain], config_file_path()))
                config_file_save_membership_role(subdomain, memberships[subdomain], state.debug)
            else:
                if state.verbose:
                    click.echo('Membership denied.')

    @classmethod
    def _get_and_save_api_key(cls, state, username, auth_token):
        headers = {'Authorization': 'Token ' + auth_token}
        silent_state = state.make_new_silent()
        result, error = ProfileAPIKeyAPIEndPoint(silent_state).read(username, **headers)
        if error:
            return ArcsecondAPI._echo_error(state, error)
        if result:
            api_key = result['api_key']
            config_file_save_api_key(api_key, username, state.debug)
            if state.verbose:
                click.echo('Successful API key retrieval and storage in {}. Enjoy.'.format(config_file_path()))
            return result

    @classmethod
    def is_logged_in(cls, state=None):
        return config_file_read_api_key() is not None

    @classmethod
    def login(cls, username, password, subdomain, state=None):
        state = state or State()
        result, error = AuthAPIEndPoint(state).login(username, password)
        if error:
            return ArcsecondAPI._echo_error(state, error)
        elif result:
            result = ArcsecondAPI._get_and_save_api_key(state, username, result['key'])
            if subdomain:
                ArcsecondAPI._check_organisation_membership(state, username, subdomain)
            return result

    @classmethod
    def register(cls, username, email, password1, password2, state=None):
        state = state or State()
        result, error = AuthAPIEndPoint(state).register(username, email, password1, password2)
        if error:
            return ArcsecondAPI._echo_request_error(state, error)
        if result:
            return ArcsecondAPI._get_and_save_api_key(state, username, result['key'])
