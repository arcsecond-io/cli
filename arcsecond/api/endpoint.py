from urllib.parse import urlencode

import click
import requests

from arcsecond.api.config import Config
from arcsecond.api.constants import API_AUTH_PATH_LOGIN, API_AUTH_PATH_REGISTER
from arcsecond.api.error import ArcsecondError
from arcsecond.options import State

SAFE_METHODS = ['GET', 'OPTIONS']
WRITABLE_MEMBERSHIPS = ['superadmin', 'admin', 'member']


class APIEndPoint(object):
    def __init__(self, name: str, state=None, subresource=''):
        self.__name = name
        # Provided state may contain overriding access_key or upload_key to be used.
        self.__state = state or State()
        self.__config = Config(self.__state.config_section)
        self.__subdomain = getattr(state, 'organisation', '')
        self.__subresource = subresource
        self.__headers = {}

    @property
    def name(self):
        return self.__name

    def _get_base_url(self):
        return self.__state.api_server

    def _build_url(self, *args, **filters):
        fragments = [f for f in [self.__subdomain, ] + list(args) + [self.__subresource, ] if f and len(f) > 0]
        url = self._get_base_url() + '/' + '/'.join(fragments) + '/'
        query = '?' + urlencode(filters) if len(filters) > 0 else ''
        return url + query

    def _list_url(self, **filters):
        return self._build_url(self.__name, **filters)

    def _detail_url(self, uuid_or_id):
        return self._build_url(self.__name, str(uuid_or_id))

    def use_headers(self, headers):
        self.__headers = headers

    def list(self, **filters):
        return self._perform_request(self._list_url(**filters), 'get', None)

    def create(self, payload):
        return self._perform_request(self._list_url(), 'post', payload)

    def read(self, id_name_uuid):
        return self._perform_request(self._detail_url(id_name_uuid), 'get', None)

    def update(self, id_name_uuid, payload):
        return self._perform_request(self._detail_url(id_name_uuid), 'patch', payload)

    def delete(self, id_name_uuid):
        return self._perform_request(self._detail_url(id_name_uuid), 'delete', None)

    def _perform_request(self, url, method_name, payload):
        headers = self._check_and_set_auth_key(self.__headers or {}, url)
        if payload:
            # Filtering None values out of payload.
            payload = {k: v for k, v in payload.items() if v is not None}

        if self.__state.verbose:
            click.echo('Sending {} request to {}'.format(method_name, url))

        method = getattr(requests, method_name.lower())
        response = method(url, json=payload, headers=headers, timeout=60)

        if isinstance(response, dict):
            # Responses of standard JSON payload requests are dict
            return response, None
        elif response is not None:
            if 200 <= response.status_code < 300:
                return response.json() if response.text else {}, None
            else:
                return None, response.text
        else:
            return None, ArcsecondError()

    def _check_and_set_auth_key(self, headers, url):
        if API_AUTH_PATH_REGISTER in url or API_AUTH_PATH_LOGIN in url or 'Authorization' in headers.keys():
            return headers

        # Choose the strongest key first
        auth_key = self.__state.access_key or self.__state.upload_key

        if auth_key is None:
            if self.__state.verbose:
                click.echo('Checking local API|Upload key... ', nl=False)

            # Choose the strongest key first
            auth_key = self.__config.access_key or self.__config.upload_key
            if not auth_key:
                raise ArcsecondError('Missing auth keys (API or Upload). You must login first: $ arcsecond login')

        headers['X-Arcsecond-API-Authorization'] = 'Key ' + auth_key

        if self.__state.verbose:
            key_str = auth_key[:3] + 9 * '*'
            click.echo(f'OK (\'X-Arcsecond-API-Authorization\' = \'Key {key_str}\'')

        return headers

    def _echo_spinner_request_result(self, error, response):
        click.echo()
        if error:
            click.echo('Request failed.')
        elif response:
            click.echo('Request successful.')
