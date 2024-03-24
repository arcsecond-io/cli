from urllib.parse import urlencode

import click
import requests

from arcsecond.api.config import ArcsecondConfig
from arcsecond.api.constants import API_AUTH_PATH_LOGIN, API_AUTH_PATH_REGISTER
from arcsecond.api.error import ArcsecondError

SAFE_METHODS = ['GET', 'OPTIONS']
WRITABLE_MEMBERSHIPS = ['superadmin', 'admin', 'member']


class ArcsecondAPIEndpoint(object):
    def __init__(self, config: ArcsecondConfig, path: str, subdomain: str = '', subresource: str = ''):
        self.__config = config
        self.__path = path
        self.__subdomain = subdomain
        self.__subresource = subresource
        self.__headers = {}

    @property
    def path(self):
        return self.__path

    def _get_base_url(self):
        return self.__config.api_server

    def _build_url(self, *args, **filters):
        fragments = [f for f in [self.__subdomain, ] + list(args) + [self.__subresource, ] if f and len(f) > 0]
        url = self._get_base_url() + '/' + '/'.join(fragments) + '/'
        query = '?' + urlencode(filters) if len(filters) > 0 else ''
        return url + query

    def _list_url(self, **filters):
        return self._build_url(self.__path, **filters)

    def _detail_url(self, uuid_or_id):
        return self._build_url(self.__path, str(uuid_or_id))

    def list(self, **filters):
        return self._perform_request(self._list_url(**filters), 'get')

    def read(self, id_name_uuid):
        return self._perform_request(self._detail_url(id_name_uuid), 'get')

    def create(self, json=None, data=None, headers=None):
        print(json, data, headers)
        return self._perform_request(self._list_url(),
                                     'post',
                                     json=json,
                                     data=data,
                                     headers=headers)

    def update(self, id_name_uuid, json=None, data=None, headers=None):
        return self._perform_request(self._detail_url(id_name_uuid),
                                     'patch',
                                     json=json,
                                     data=data,
                                     headers=headers)

    def delete(self, id_name_uuid):
        return self._perform_request(self._detail_url(id_name_uuid), 'delete')

    def _perform_request(self, url, method_name, json=None, data=None, headers=None):
        if self.__config.verbose:
            click.echo('Sending {} request to {}'.format(method_name, url))

        headers = self._check_and_set_auth_key(headers or {}, url)
        method = getattr(requests, method_name.lower())
        response = method(url, json=json, data=data, headers=headers, timeout=60)

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
        auth_key = self.__config.access_key or self.__config.upload_key

        if auth_key is None:
            if self.__config.verbose:
                click.echo('Checking local API|Upload key... ', nl=False)

            # Choose the strongest key first
            auth_key = self.__config.access_key or self.__config.upload_key
            if not auth_key:
                raise ArcsecondError('Missing auth keys (API or Upload). You must login first: $ arcsecond login')

        headers['X-Arcsecond-API-Authorization'] = 'Key ' + auth_key

        if self.__config.verbose:
            key_str = auth_key[:3] + 9 * '*'
            click.echo(f'\'X-Arcsecond-API-Authorization\' = \'Key {key_str}\'')

        return headers

    def _echo_spinner_request_result(self, error, response):
        click.echo()
        if error:
            click.echo('Request failed.')
        elif response:
            click.echo('Request successful.')
