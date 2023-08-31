import copy
from urllib.parse import urlencode

import click
import requests

from arcsecond.api.constants import (
    API_AUTH_PATH_LOGIN,
    API_AUTH_PATH_REGISTER
)
from arcsecond.api.error import ArcsecondError
from arcsecond.config import (
    config_file_read_api_key,
    config_file_read_upload_key
)
from arcsecond.options import State

SAFE_METHODS = ['GET', 'OPTIONS']
WRITABLE_MEMBERSHIPS = ['superadmin', 'admin', 'member']

EVENT_METHOD_WILL_START = 'EVENT_METHOD_WILL_START'
EVENT_METHOD_DID_FINISH = 'EVENT_METHOD_DID_FINISH'
EVENT_METHOD_DID_FAIL = 'EVENT_METHOD_DID_FAIL'
EVENT_METHOD_PROGRESS_PERCENT = 'EVENT_METHOD_PROGRESS_PERCENT'


class APIEndPoint(object):
    name = None

    def __init__(self, state=None, prefix=''):
        # Provided state may contain overriding api_key or upload_key to be used.
        self.state = state or State()
        self.prefix = prefix
        self.organisation = getattr(state, 'organisation', '')
        self.headers = {}

    def _get_base_url(self):
        return self.state.api_server

    def _root_url(self):
        prefix = self.prefix
        if len(prefix) and prefix[0] != '/':
            prefix = '/' + prefix
        return self._get_base_url() + prefix

    def _build_url(self, *args, **filters):
        fragments = [f for f in [self.organisation, self.prefix] + list(args) if f]
        url = self._get_base_url() + '/' + '/'.join(fragments) + '/'
        query = '?' + urlencode(filters) if len(filters) > 0 else ''
        return url + query

    def _root_open_url(self):
        pass

    def _get_list_url(self, **filters):
        raise Exception('You must override this method.')

    def _get_detail_url(self, name_or_id):
        raise Exception('You must override this method.')

    def _open_url(self, name_or_id):
        raise Exception('You must override this method.')

    def use_headers(self, headers):
        self.headers = headers

    def list(self, **filters):
        return self._perform_request(self._get_list_url(**filters), 'get', None)

    def create(self, payload):
        return self._perform_request(self._get_list_url(), 'post', payload)

    def read(self, id_name_uuid):
        return self._perform_request(self._get_detail_url(id_name_uuid), 'get', None)

    def update(self, id_name_uuid, payload):
        return self._perform_request(self._get_detail_url(id_name_uuid), 'patch', payload)

    def delete(self, id_name_uuid):
        return self._perform_request(self._get_detail_url(id_name_uuid), 'delete', None)

    def _perform_request(self, url, method_name, payload):
        method, json, headers = self._prepare_request(url, method_name, payload)

        if self.state.verbose:
            click.echo(f'Sending {method_name} request to {url}')
            if json:
                self._echo_spinner_request_payload(json)

        try:
            response = method(url, json=json, headers=headers)
        except Exception as e:
            return None, ArcsecondError(str(e))
        else:
            if isinstance(response, dict):
                # Responses of standard JSON payload requests are dict
                return response
            elif response is not None:
                if 200 <= response.status_code < 300:
                    return response.json() if response.text else {}, None
                else:
                    return None, ArcsecondError(response.text)
            else:
                return None, ArcsecondError('No response?')

    def _prepare_request(self, url, method_name, payload):
        assert (url and method_name)

        if self.state.verbose:
            click.echo('Preparing request...')

        if not isinstance(method_name, str) or callable(method_name):
            raise ArcsecondError('Invalid HTTP request method {}. '.format(str(method_name)))

        # Check API key, hence login state. Must do before check for org.
        headers = self._check_and_set_auth_key(self.headers or {}, url)
        method = getattr(requests, method_name.lower()) if isinstance(method_name, str) else method_name

        if payload:
            # Filtering None values out of payload.
            payload = {k: v for k, v in payload.items() if v is not None}

        return method, payload, headers

    def _check_and_set_auth_key(self, headers, url):
        if API_AUTH_PATH_REGISTER in url or API_AUTH_PATH_LOGIN in url or 'Authorization' in headers.keys():
            return headers

        # Choose the strongest key first
        auth_key = self.state.api_key or self.state.upload_key

        if auth_key is None:
            if self.state.verbose:
                click.echo('Checking local API|Upload key... ', nl=False)

            # Choose the strongest key first
            auth_key = config_file_read_api_key(self.state.config_section)
            if not auth_key:
                auth_key = config_file_read_upload_key(self.state.config_section)
                if not auth_key:
                    raise ArcsecondError('Missing auth keys (API or Upload). You must login first: $ arcsecond login')

        headers['X-Arcsecond-API-Authorization'] = 'Key ' + auth_key

        if self.state.verbose:
            key_str = auth_key[:3] + 9 * '*'
            click.echo(f'OK (\'X-Arcsecond-API-Authorization\' = \'Key {key_str}\'')

        return headers

    def _echo_spinner_request_payload(self, payload):
        if isinstance(payload, dict):
            payload_copy = copy.deepcopy(payload)
            for key in ['password', 'api_key', 'upload_key', 'key']:
                if key in payload_copy.keys():
                    payload_copy[key] = payload_copy[key][:3] + 9 * '*'
            click.echo(f'Payload: {payload_copy}')
        else:
            click.echo(f'Payload: {payload}')

    def _echo_spinner_request_result(self, error, response):
        click.echo()
        if error:
            click.echo('Request failed.')
        elif response:
            click.echo('Request successful.')
