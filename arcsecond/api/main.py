# -*- coding: utf-8 -*-

import json
import pprint
import types
import webbrowser
from json import JSONDecodeError
from typing import Optional, Type

import click
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

from arcsecond.config import (config_file_clear_api_key,
                              config_file_clear_upload_key,
                              config_file_is_logged_in,
                              config_file_path,
                              config_file_read_api_key,
                              config_file_read_api_server,
                              config_file_read_organisation_memberships,
                              config_file_read_upload_key,
                              config_file_read_username,
                              config_file_save_api_key,
                              config_file_save_api_server,
                              config_file_save_organisation_membership,
                              config_file_save_shared_key,
                              config_file_save_upload_key,
                              config_file_save_username)
from arcsecond.options import State
from .auth import AuthAPIEndPoint
from .endpoints import (ActivitiesAPIEndPoint, AsyncFileUploader, CalibrationsAPIEndPoint, CataloguesAPIEndPoint,
                        DataFilesAPIEndPoint, DatasetsAPIEndPoint, ExoplanetsAPIEndPoint, FindingChartsAPIEndPoint,
                        InstrumentsAPIEndPoint, MembersAPIEndPoint, NightLogsAPIEndPoint, ObjectsAPIEndPoint,
                        ObservationsAPIEndPoint, ObservingRunsAPIEndPoint, ObservingSitesAPIEndPoint,
                        OrganisationUploadKeysAPIEndPoint, OrganisationsAPIEndPoint, PersonalProfileAPIEndPoint,
                        ProfileAPIEndPoint, ProfileAPIKeyAPIEndPoint, ProfileSharedKeysAPIEndPoint,
                        ProfileUploadKeyAPIEndPoint, SatellitesAPIEndPoint, StandardStarsAPIEndPoint,
                        TelegramsATelAPIEndPoint, TelescopesAPIEndPoint)
from .endpoints._base import APIEndPoint
from .error import (
    ArcsecondInvalidEndpointError,
    ArcsecondMissingArgumentError,
    ArcsecondNotLoggedInError,
    ArcsecondTooManyPrefixesError
)

pp = pprint.PrettyPrinter(indent=4, depth=5)
ECHO_PREFIX = u' • '
ECHO_ERROR_PREFIX = u' • [error] '

__all__ = ["ArcsecondAPI", "AsyncFileUploader"]

ENDPOINTS = [ActivitiesAPIEndPoint,
             CalibrationsAPIEndPoint,
             CataloguesAPIEndPoint,
             DataFilesAPIEndPoint,
             DatasetsAPIEndPoint,
             ExoplanetsAPIEndPoint,
             FindingChartsAPIEndPoint,
             InstrumentsAPIEndPoint,
             MembersAPIEndPoint,
             NightLogsAPIEndPoint,
             ObjectsAPIEndPoint,
             ObservationsAPIEndPoint,
             ObservingRunsAPIEndPoint,
             ObservingSitesAPIEndPoint,
             OrganisationsAPIEndPoint,
             OrganisationUploadKeysAPIEndPoint,
             PersonalProfileAPIEndPoint,
             ProfileAPIEndPoint,  # Do not expose ProfileAPIKeyAPIEndPoint, ProfileUploadKeyAPIEndPoint etc...
             SatellitesAPIEndPoint,
             StandardStarsAPIEndPoint,
             TelescopesAPIEndPoint,
             TelegramsATelAPIEndPoint]

# Tricky but values must NOT have leading slash, but MUST have trailing one...
VALID_PREFIXES = {'dataset': 'datasets/'}


def get_api_state(state=None, **kwargs):
    if 'api' in kwargs.keys():
        kwargs.update(api_name=kwargs.get('api'))

    state = state or State(is_using_cli=False)
    state.update(**kwargs)

    if state.api_name and not state.api_server:
        state.api_server = config_file_read_api_server(state.api_name)

    if state.verbose and state.is_using_cli:
        click.echo(f'{ECHO_PREFIX}{state.api_name}{ECHO_PREFIX}')

    return state


def set_api_factory(cls):
    def factory(endpoint_class, state=None, **kwargs):
        return ArcsecondAPI(endpoint_class, state, **kwargs)

    for endpoint_class in ENDPOINTS:
        setattr(cls, endpoint_class.name, staticmethod(types.MethodType(factory, endpoint_class)))

    return cls


@set_api_factory
class ArcsecondAPI(object):
    def __init__(self, endpoint_class=None, state=None, **kwargs):
        self.state = get_api_state(state, **kwargs)
        self._check_logged_in()  # Always require to be authenticated (-> one needs it to count API requests)
        prefix = self._check_prefix(kwargs)
        endpoint_class = self._check_endpoint_class(endpoint_class)
        self.endpoint = endpoint_class(self.state, prefix=prefix) if endpoint_class else None

    def __str__(self):
        return self.endpoint.name or '' if self.endpoint else ''

    def _check_logged_in(self):
        if not self.__class__.is_logged_in(self.state):
            raise ArcsecondNotLoggedInError()

    def _check_prefix(self, kwargs):
        prefix = kwargs.get('prefix') or ''
        possible_prefixes = set(kwargs.keys()).intersection(VALID_PREFIXES.keys())
        if len(possible_prefixes) > 1:
            raise ArcsecondTooManyPrefixesError(possible_prefixes)
        elif len(possible_prefixes) == 1 and prefix:
            raise ArcsecondTooManyPrefixesError([possible_prefixes.pop(), prefix])
        elif len(possible_prefixes) == 1 and not prefix:
            prefix_key = possible_prefixes.pop()
            prefix = VALID_PREFIXES[prefix_key] + kwargs[prefix_key]
        return prefix

    def _check_endpoint_class(self, endpoint_class: Optional[Type[APIEndPoint]]) -> APIEndPoint.__class__:
        if endpoint_class is not None and endpoint_class not in ENDPOINTS:
            raise ArcsecondInvalidEndpointError(endpoint_class, ENDPOINTS)
        return endpoint_class

    def list(self, **filters):
        return self._handle_endpoint_response(self.endpoint.list(**filters))

    def create(self, payload, callback=None):
        return self._handle_endpoint_response(self.endpoint.create(payload, callback=callback))

    def read(self, id_name_uuid):
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
            return self._handle_endpoint_response(self.endpoint.read(id_name_uuid))

    def update(self, id_name_uuid, payload, callback=None):
        return self._handle_endpoint_response(self.endpoint.update(id_name_uuid, payload, callback=callback))

    def delete(self, id_name_uuid):
        return self._handle_endpoint_response(self.endpoint.delete(id_name_uuid))

    def _handle_endpoint_response(self, response):
        result, error = response
        if result is not None:  # check against None, to avoid skipping empty lists.
            ArcsecondAPI._echo_result(self.state, result)
        if error is not None:
            ArcsecondAPI._echo_error(self.state, error)
        return result, error

    @classmethod
    def _echo_message(cls, state, message):
        if state.verbose:
            click.echo(message)

    @classmethod
    def _echo_result(cls, state, result):
        if not state.is_using_cli:
            return
        # A create or update method with a file to upload will return a tuple made of
        # a FileUploader and None. Hence, nothing to print outside.
        if isinstance(result, dict) or isinstance(result, list):
            if isinstance(result, dict):
                for key in ['password', 'api_key', 'upload_key', 'key']:
                    if key in result.keys():
                        result[key] = result[key][:3] + 9 * '*'
            json_str = json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)
            # .strip() avoids the empty newline
            click.echo(highlight(json_str, JsonLexer(), TerminalFormatter()).strip())

    @classmethod
    def _echo_error(cls, state, error):
        if not state.is_using_cli:
            return

        if state:
            click.echo(click.style(error, fg='red'))
        else:
            try:
                json_obj = json.loads(error)
            except JSONDecodeError:
                message = str(error)
            else:
                message = ''
                if 'detail' in json_obj.keys():
                    detail = json_obj['detail']
                    message = ', '.join(detail) if isinstance(detail, list) else detail
                elif 'error' in json_obj.keys():
                    error = json_obj['error']
                    message = ', '.join(error) if isinstance(error, list) else error
                elif 'non_field_errors' in json_obj.keys():
                    errors = json_obj['non_field_errors']
                    message = ', '.join(errors) if isinstance(errors, list) else str(errors)
                else:
                    message = str(error)
            click.echo(click.style(ECHO_PREFIX + message, fg='red'))

    @classmethod
    def _get_and_save_shared_keys_for_organisation(cls, state, username, auth_token, organisation):
        # To get Upload keys one must fetch it with Auth token obtained via login.
        endpoint = ProfileSharedKeysAPIEndPoint(state.make_new_silent())
        endpoint.use_headers({'Authorization': 'Token ' + auth_token})
        result, error = endpoint.read(username)
        if error:
            ArcsecondAPI._echo_error(state, error)
        if result:
            upload_key_dict = next((x for x in result if result.get('organisation') == organisation), None)
            if upload_key_dict:
                config_file_save_shared_key(upload_key_dict['key'], username, organisation, state.config_section)
                msg = f'Successful Shared key retrieval and storage in {config_file_path()}. Enjoy.'
                ArcsecondAPI._echo_message(state, msg)
            else:
                # TODO: deal with error
                pass
        return result, error

    @classmethod
    def register(cls, username, email, password1, password2, state=None, **kwargs):
        state = get_api_state(state, **kwargs)
        result, error = AuthAPIEndPoint(state).register(username, email, password1, password2)
        if error:
            ArcsecondAPI._echo_error(state, error)
        elif result:
            # We replace result and error of register with that of api key
            result, error = ArcsecondAPI._get_and_save_api_key(state, username, result['key'])
        return result, error

    @classmethod
    def login(cls, username, password, state=None, *args, **kwargs):
        state = get_api_state(state, **kwargs)
        result, error = AuthAPIEndPoint(state).login(username, password)
        if error:
            ArcsecondAPI._echo_error(state, error)
        elif result:
            auth_token = result['token']
            profile, error = ArcsecondAPI._check_memberships(state, username, auth_token)
            if profile:
                # Update username with that of returned profile in case we logged in with email address.
                username = profile.get('username', username)
                config_file_save_username(username, section=state.config_section)

            # We replace result and error of login with that of key check.
            if 'api_key' in kwargs.keys() and bool(kwargs['api_key']):
                result, error = ArcsecondAPI._get_and_save_api_key(state, username, auth_token)
            if 'upload_key' in kwargs.keys() and bool(kwargs['upload_key']):
                result, error = ArcsecondAPI._get_and_save_upload_key(state, username, auth_token)
            if 'shared_keys' in kwargs.keys() and bool(kwargs['shared_keys']):
                if 'organisation' not in kwargs.keys():
                    raise ArcsecondMissingArgumentError('organisation')
                organisation = kwargs.get('organisation')
                result, error = ArcsecondAPI._get_and_save_shared_keys_for_organisation(state,
                                                                                        username,
                                                                                        auth_token,
                                                                                        organisation)
        return result, error

    @classmethod
    def _get_and_save_api_key(cls, state, username, auth_token):
        ArcsecondAPI._echo_message(state, 'Fetching API Key...')
        # To get API key one must fetch it with Auth token obtained via login.
        endpoint = ProfileAPIKeyAPIEndPoint(state.make_new_silent())
        endpoint.use_headers({'Authorization': 'Token ' + auth_token})
        result, error = endpoint.read(username)
        if error:
            ArcsecondAPI._echo_error(state, error)
        if result:
            config_file_save_api_key(result['api_key'], username, state.config_section)
            msg = f'Successful API key retrieval and storage in {config_file_path()}. Enjoy.'
            ArcsecondAPI._echo_message(state, msg)
        return result, error

    @classmethod
    def _get_and_save_upload_key(cls, state, username, auth_token):
        ArcsecondAPI._echo_message(state, 'Fetching Upload Key...')
        # To get API key one must fetch it with Auth token obtained via login.
        endpoint = ProfileUploadKeyAPIEndPoint(state.make_new_silent())
        endpoint.use_headers({'Authorization': 'Token ' + auth_token})
        result, error = endpoint.read(username)
        if error:
            ArcsecondAPI._echo_error(state, error)
        if result:
            config_file_save_upload_key(result['upload_key'], username, state.config_section)
            msg = f'Successful Upload key retrieval and storage in {config_file_path()}. Enjoy.'
            ArcsecondAPI._echo_message(state, msg)
        return result, error

    @classmethod
    def _check_memberships(cls, state, username, auth_token):
        ArcsecondAPI._echo_message(state, 'Checking Organisation Memberships...')
        endpoint = PersonalProfileAPIEndPoint(state.make_new_silent())
        endpoint.use_headers({'Authorization': 'Token ' + auth_token})
        profile, error = endpoint.read(username)
        if error:
            ArcsecondAPI._echo_error(state, error)
        else:
            memberships = {m['organisation']['subdomain']: m['role'] for m in profile['memberships']}
            if len(memberships.keys()) > 0:
                for membership in memberships.keys():
                    msg = f'Membership to "{membership}" organisation confirmed. Role is "{memberships[membership]}".'
                    ArcsecondAPI._echo_message(state, msg)
                    config_file_save_organisation_membership(membership,
                                                             memberships[membership],
                                                             state.config_section)
            else:
                ArcsecondAPI._echo_message(state, 'Membership {membership} denied.')
        return profile, error

    @classmethod
    def is_logged_in(cls, state: Optional[State] = None, **kwargs) -> bool:
        state = get_api_state(state, **kwargs)
        return config_file_is_logged_in(section=state.config_section)

    @classmethod
    def username(cls, state: Optional[State] = None, **kwargs) -> str:
        state = get_api_state(state, **kwargs)
        return config_file_read_username(section=state.config_section) or ''

    @classmethod
    def get_api_name(cls, state: Optional[State] = None, **kwargs) -> str:
        state = get_api_state(state, **kwargs)
        return config_file_read_api_server(section=state.config_section) or ''

    @classmethod
    def set_api_name(cls, address: str, state: Optional[State] = None, **kwargs) -> str:
        kwargs.update(api_server=address)
        state = get_api_state(state, **kwargs)
        return config_file_save_api_server(address, section=state.config_section)

    @classmethod
    def api_key(cls, state: Optional[State] = None, **kwargs) -> str:
        state = get_api_state(state, **kwargs)
        return config_file_read_api_key(section=state.config_section) or ''

    @classmethod
    def upload_key(cls, state: Optional[State] = None, **kwargs) -> str:
        state = get_api_state(state, **kwargs)
        return config_file_read_upload_key(section=state.config_section) or ''

    @classmethod
    def clear_api_key(cls, key_name, state: Optional[State] = None, **kwargs) -> str:
        state = get_api_state(state, **kwargs)
        return config_file_clear_api_key(section=state.config_section) or ''

    @classmethod
    def clear_upload_key(cls, key_name, state: Optional[State] = None, **kwargs) -> str:
        state = get_api_state(state, **kwargs)
        return config_file_clear_upload_key(section=state.config_section) or ''

    @classmethod
    def memberships(cls, state: Optional[State] = None, **kwargs):
        state = get_api_state(state, **kwargs)
        raw_memberships = config_file_read_organisation_memberships(section=state.config_section)
        return {m: raw_memberships[m] for m in raw_memberships}
