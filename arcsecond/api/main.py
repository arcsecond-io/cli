# -*- coding: utf-8 -*-

import json
import pprint
import types
import webbrowser

import click
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

from arcsecond.config import (config_file_path,
                              config_file_read_api_key,
                              config_file_save_api_key,
                              config_file_read_username,
                              config_file_read_organisation_memberships,
                              config_file_save_organisation_membership)

from arcsecond.options import State
from .auth import AuthAPIEndPoint
from .error import ArcsecondInvalidEndpointError, ArcsecondNotLoggedInError, ArcsecondTooManyPrefixesError

from .endpoints import (ActivitiesAPIEndPoint, CataloguesAPIEndPoint, DatasetsAPIEndPoint, ExoplanetsAPIEndPoint,
                        DataFilesAPIEndPoint, FindingChartsAPIEndPoint, InstrumentsAPIEndPoint, NightLogAPIEndPoint,
                        ObjectsAPIEndPoint, ObservingRunsAPIEndPoint, ObservingSitesAPIEndPoint,
                        PersonalProfileAPIEndPoint, ProfileAPIEndPoint, ProfileAPIKeyAPIEndPoint, SatellitesAPIEndPoint,
                        StandardStarsAPIEndPoint, TelegramsATelAPIEndPoint, TelescopesAPIEndPoint)

from .endpoints._base import AsyncFileUploader

pp = pprint.PrettyPrinter(indent=4, depth=5)
ECHO_PREFIX = u' • '
ECHO_ERROR_PREFIX = u' • [error] '

__all__ = ["ArcsecondAPI", "AsyncFileUploader"]

ENDPOINTS = [ActivitiesAPIEndPoint,
             CataloguesAPIEndPoint,
             DatasetsAPIEndPoint,
             ExoplanetsAPIEndPoint,
             DataFilesAPIEndPoint,
             FindingChartsAPIEndPoint,
             InstrumentsAPIEndPoint,
             NightLogAPIEndPoint,
             ObjectsAPIEndPoint,
             ObservingRunsAPIEndPoint,
             ObservingSitesAPIEndPoint,
             PersonalProfileAPIEndPoint,
             ProfileAPIEndPoint,  # And not ProfileAPIKeyAPIEndPoint...
             SatellitesAPIEndPoint,
             StandardStarsAPIEndPoint,
             TelescopesAPIEndPoint,
             TelegramsATelAPIEndPoint]

# Tricky but values must NOT have leading slash, but MUST have trailing one...
VALID_PREFIXES = {'dataset': 'datasets/'}


def get_api_state(state=None, **kwargs):
    state = state or State(is_using_cli=False)

    if 'debug' in kwargs.keys():
        state.debug = kwargs.get('debug')
    if 'verbose' in kwargs.keys():
        state.verbose = kwargs.get('verbose')
    if 'organisation' in kwargs.keys():
        state.organisation = kwargs.get('organisation')

    return state


def set_api_factory(cls):
    def factory(endpoint_class, state=None, **kwargs):
        return ArcsecondAPI(endpoint_class, state, **kwargs)

    for endpoint_class in ENDPOINTS:
        func_name = 'build_' + endpoint_class.name + '_api'
        setattr(cls, func_name, staticmethod(types.MethodType(factory, endpoint_class)))

    return cls


@set_api_factory
class Arcsecond(object):
    @classmethod
    def is_logged_in(cls, state=None, **kwargs):
        return ArcsecondAPI.is_logged_in(state, **kwargs)

    @classmethod
    def username(cls, state=None, **kwargs):
        return ArcsecondAPI.username(state, **kwargs)

    @classmethod
    def memberships(cls, state=None, **kwargs):
        return ArcsecondAPI.memberships(state, **kwargs)

    @classmethod
    def login(cls, username, password, subdomain, state=None):
        return ArcsecondAPI.login(username, password, subdomain, state)

    @classmethod
    def register(cls, username, email, password1, password2, state=None):
        return ArcsecondAPI.register(username, email, password1, password2, state)


class ArcsecondAPI(object):
    def __init__(self, endpoint_class=None, state=None, **kwargs):
        self.state = get_api_state(state, **kwargs)

        if not self.__class__.is_logged_in(self.state):
            raise ArcsecondNotLoggedInError()

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
    def pretty_print_dict(cls, d):
        json_str = json.dumps(d, indent=4, sort_keys=True, ensure_ascii=False)
        click.echo(highlight(json_str, JsonLexer(), TerminalFormatter()).strip())  # .strip() avoids the empty newline

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
                detail_msg = ', '.join(json_obj['detail']) if isinstance(json_obj['detail'], list) else json_obj['detail']
                click.echo(ECHO_ERROR_PREFIX + detail_msg)
            elif 'error' in json_obj.keys():
                error_msg = ', '.join(json_obj['error']) if isinstance(json_obj['error'], list) else json_obj['error']
                click.echo(ECHO_ERROR_PREFIX + error_msg)
            elif 'non_field_errors' in json_obj.keys():
                errors = json_obj['non_field_errors']
                message = ', '.join(errors) if isinstance(error, list) else str(errors)
                click.echo(ECHO_ERROR_PREFIX + message)
            else:
                click.echo(ECHO_PREFIX + str(error))

    def _echo_response(self, response):
        if isinstance(response, AsyncFileUploader):
            return response
        result, error = response
        if result is not None:  # check against None, to avoid skipping empty lists.
            return ArcsecondAPI._echo_result(self.state, result)
        if error is not None:
            return ArcsecondAPI._echo_error(self.state, error)

    def _check_endpoint_class(self, endpoint):
        if endpoint is not None and endpoint not in ENDPOINTS:
            raise ArcsecondInvalidEndpointError(endpoint, ENDPOINTS)
        return endpoint

    def list(self, name=None, **headers):
        return self._echo_response(self.endpoint.list(name, **headers))

    def create(self, payload, callback=None, **headers):
        return self._echo_response(self.endpoint.create(payload, callback=callback, **headers))

    def read(self, id_name_uuid, **headers):
        if not id_name_uuid:
            return self.list(name=None, **headers)

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
    def _check_organisation_membership(cls, state, username, subdomain):
        if state.verbose:
            click.echo('Checking Membership of Organisation with subdomain "{}"...'.format(subdomain))
        profile, error = PersonalProfileAPIEndPoint(state.make_new_silent()).read(username)
        if error:
            ArcsecondAPI._echo_error(state, error)
        else:
            memberships = {m['organisation']['subdomain']: m['role'] for m in profile['memberships']}
            if subdomain in memberships.keys():
                if state.verbose:
                    click.echo('Membership confirmed. Role is "{}", stored in {}.'
                               .format(memberships[subdomain], config_file_path()))
                config_file_save_organisation_membership(subdomain, memberships[subdomain], state.config_section())
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
            config_file_save_api_key(api_key, username, state.config_section())
            if state.verbose:
                click.echo('Successful API key retrieval and storage in {}. Enjoy.'.format(config_file_path()))
            return result

    @classmethod
    def is_logged_in(cls, state=None, **kwargs):
        state = get_api_state(state, **kwargs)
        return config_file_read_api_key(section=state.config_section()) is not None

    @classmethod
    def username(cls, state=None, **kwargs):
        state = get_api_state(state, **kwargs)
        return config_file_read_username(section=state.config_section()) or ''

    @classmethod
    def memberships(cls, state=None, **kwargs):
        state = get_api_state(state, **kwargs)
        return config_file_read_organisation_memberships(section=state.config_section())

    @classmethod
    def login(cls, username, password, subdomain, state=None):
        state = get_api_state(state)
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
        state = get_api_state(state)
        result, error = AuthAPIEndPoint(state).register(username, email, password1, password2)
        if error:
            return ArcsecondAPI._echo_error(state, error)
        elif result:
            return ArcsecondAPI._get_and_save_api_key(state, username, result['key'])
