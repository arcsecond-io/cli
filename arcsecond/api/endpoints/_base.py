import copy
from urllib.parse import urlencode

import click
import requests
from progress.bar import Bar
from progress.spinner import Spinner
from requests_toolbelt.multipart import encoder

from arcsecond.api.constants import (
    API_AUTH_PATH_LOGIN,
    API_AUTH_PATH_REGISTER
)
from arcsecond.api.error import ArcsecondError
from arcsecond.api.helpers import extract_multipart_encoder_file_fields
from arcsecond.config import (
    config_file_read_api_key,
    config_file_read_upload_key
)
from arcsecond.options import State
from ._fileuploader import AsyncFileUploader

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

    def _list_url(self, **filters):
        raise Exception('You must override this method.')

    def _detail_url(self, name_or_id):
        raise Exception('You must override this method.')

    def _open_url(self, name_or_id):
        raise Exception('You must override this method.')

    def use_headers(self, headers):
        self.headers = headers

    def list(self, **filters):
        return self._perform_request(self._list_url(**filters), 'get', None, None)

    def create(self, payload, callback=None):
        # If a file is provided as part of the payload, a instance of AsyncFileUploader is returned
        # in place of a standard JSON body response.
        return self._perform_request(self._list_url(), 'post', payload, callback)

    def read(self, id_name_uuid):
        return self._perform_request(self._detail_url(id_name_uuid), 'get', None, None)

    def update(self, id_name_uuid, payload, callback=None):
        return self._perform_request(self._detail_url(id_name_uuid), 'patch', payload, callback)

    def delete(self, id_name_uuid):
        return self._perform_request(self._detail_url(id_name_uuid), 'delete', None, None)

    def _perform_request(self, url, method, payload, callback=None):
        method_name, method, payload, headers = self._prepare_request(url, method, payload)

        payload, fields = extract_multipart_encoder_file_fields(payload)
        if fields is None:
            # Standard JSON sync request
            return self._perform_spinner_request(url, method, method_name, None, payload, **headers)
        else:
            # Process payload synchronously nonetheless
            if payload:
                self._perform_spinner_request(url, method, method_name, None, payload, **headers)

            # File upload
            upload_monitor = self._build_dynamic_upload_data(fields, callback)
            headers.update(**{'Content-Type': upload_monitor.content_type})

            if self.state.is_using_cli:
                return self._perform_spinner_request(url, method, method_name, upload_monitor, None, **headers)
            else:
                return AsyncFileUploader(url, method, data=upload_monitor, payload=None, **headers), None

    def _prepare_request(self, url, method, payload):
        assert (url and method)

        if self.state.verbose:
            click.echo('Preparing request...')

        if not isinstance(method, str) or callable(method):
            raise ArcsecondError('Invalid HTTP request method {}. '.format(str(method)))

        # Put method name aside in its own var.
        method_name = method.upper() if isinstance(method, str) else ''

        # Check API key, hence login state. Must do before check for org.
        headers = self._check_and_set_auth_key(self.headers or {}, url)
        method = getattr(requests, method.lower()) if isinstance(method, str) else method

        if payload:
            # Filtering None values out of payload.
            payload = {k: v for k, v in payload.items() if v is not None}

        return method_name, method, payload, headers

    def _build_dynamic_upload_data(self, fields, callback=None):
        # The monitor is the data!
        encoded_data = encoder.MultipartEncoder(fields=fields)

        if self.state.is_using_cli is True and self.state.verbose:
            bar = Bar('Uploading ' + fields['file'][0], suffix='%(percent)d%%')
            return encoder.MultipartEncoderMonitor(encoded_data, lambda m: bar.goto(m.bytes_read / m.len * 100))
        elif self.state.is_using_cli is False and callback:
            return encoder.MultipartEncoderMonitor(encoded_data, lambda m: callback(EVENT_METHOD_PROGRESS_PERCENT,
                                                                                    m.bytes_read / m.len * 100))
        else:
            return encoder.MultipartEncoderMonitor(encoded_data, None)

    def _perform_spinner_request(self, url, method, method_name, data=None, payload=None, **headers):
        if self.state.verbose:
            click.echo('Sending {} request to {}'.format(method_name, url))
            if payload:
                self._echo_spinner_request_payload(payload)

        performer = AsyncFileUploader(url, method, data=data, payload=payload, **headers)
        performer.start()

        spinner = Spinner()
        while performer.is_alive():
            if self.state.verbose:
                spinner.next()

        response, error = performer.finish()

        # If we have an error and it is an ArcsecondError, raise it.
        # As for now, only ArcsecondError could be returned, and there is no
        # real point of returning both response and error below. But
        # methods in main.py expect them both.

        if error and isinstance(error, ArcsecondError):
            raise error

        if self.state.verbose:
            self._echo_spinner_request_result(error, response)

        return response, error

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
