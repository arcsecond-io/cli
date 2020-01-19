import threading
import uuid
from typing import Tuple

import click
import requests
from requests_toolbelt.multipart import encoder

from progress.spinner import Spinner
from progress.bar import Bar

from arcsecond.api.constants import (
    ARCSECOND_API_URL_DEV,
    ARCSECOND_API_URL_PROD,
    ARCSECOND_WWW_URL_DEV,
    ARCSECOND_WWW_URL_PROD,
    API_AUTH_PATH_LOGIN,
    API_AUTH_PATH_REGISTER)

from arcsecond.api.error import ArcsecondConnectionError, ArcsecondError
from arcsecond.api.helpers import extract_multipart_encoder_file_fields
from arcsecond.config import config_file_read_api_key, config_file_read_organisation_memberships
from arcsecond.options import State

SAFE_METHODS = ['GET', 'OPTIONS']
WRITABLE_MEMBERSHIPS = ['superadmin', 'admin', 'member']

EVENT_METHOD_WILL_START = 'EVENT_METHOD_WILL_START'
EVENT_METHOD_DID_FINISH = 'EVENT_METHOD_DID_FINISH'
EVENT_METHOD_DID_FAIL = 'EVENT_METHOD_DID_FAIL'
EVENT_METHOD_PROGRESS_PERCENT = 'EVENT_METHOD_PROGRESS_PERCENT'


class AsyncRequestPerformer(object):
    def __init__(self, url, method, data=None, payload=None, **headers):
        self.url = url
        self.method = method
        self.payload = payload
        self.data = data
        self.headers = headers

        self._storage = {}
        self._thread = None

    def start(self):
        if self._thread is None:
            args = (self.url, self.method, self.data, self.payload, self.headers)
            self._thread = threading.Thread(target=self._target, args=args)
        self._thread.start()

    def _target(self, url, method, data, payload, headers):
        try:
            self._storage['response'] = method(url, data=data, json=payload, headers=headers)
        except requests.exceptions.ConnectionError:
            self._storage['error'] = ArcsecondConnectionError(url)
        except Exception as e:
            self._storage['error'] = ArcsecondError(str(e))

    def join(self):
        self._thread.join()

    def is_alive(self):
        return self._thread.is_alive()

    def get_results(self):
        return self._storage.get('response'), self._storage.get('error')


class APIEndPoint(object):
    name = None

    def __init__(self, state=None, prefix=''):
        self.state = state or State()
        self.prefix = prefix
        self.organisation = state.organisation or ''

    def _get_base_url(self):
        return ARCSECOND_API_URL_DEV if self.state.debug else ARCSECOND_API_URL_PROD

    def _root_url(self):
        prefix = self.prefix
        if len(prefix) and prefix[0] != '/':
            prefix = '/' + prefix
        return self._get_base_url() + prefix

    def _build_url(self, *args):
        fragments = [f for f in [self.organisation, self.prefix] + list(args) if f]
        return self._get_base_url() + '/' + '/'.join(fragments) + '/'

    def _root_open_url(self):
        if hasattr(self.state, 'open'):
            return ARCSECOND_WWW_URL_DEV if self.state.debug is True else ARCSECOND_WWW_URL_PROD

    def _list_url(self, name=''):
        raise Exception('You must override this method.')

    def _detail_url(self, name_or_id):
        raise Exception('You must override this method.')

    def _open_url(self, name_or_id):
        raise Exception('You must override this method.')

    def _check_uuid(self, uuid_str):
        if not uuid_str:
            raise ArcsecondError('Missing UUID')
        try:
            uuid.UUID(uuid_str)
        except ValueError:
            raise ArcsecondError('Invalid UUID {}.'.format(uuid_str))

    def list(self, name='', **headers):
        return self._perform_request(self._list_url(name), 'get', None, None, **headers)

    def create(self, payload, callback=None, **headers):
        return self._perform_request(self._list_url(), 'post', payload, callback, **headers)

    def read(self, id_name_uuid, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'get', None, None, **headers)

    def update(self, id_name_uuid, payload, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'put', payload, None, **headers)

    def delete(self, id_name_uuid, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'delete', None, None, **headers)

    def _perform_request(self, url, method, payload, callback=None, **headers):
        method_name, method, payload, headers = self._prepare_request(url, method, payload, **headers)

        payload, fields = extract_multipart_encoder_file_fields(payload)
        if fields is None:
            # Standard JSON sync request
            return self._perform_spinner_request(url, method, method_name, None, payload, **headers)
        else:
            # File upload
            upload_monitor = self._build_dynamic_upload_data(fields, callback)
            headers.update(**{'Content-Type': upload_monitor.content_type})

            if self.state.is_using_cli:
                return self._perform_spinner_request(url, method, method_name, upload_monitor, None, **headers)
            else:
                return AsyncRequestPerformer(url, method, data=upload_monitor, payload=None, **headers)

    def _prepare_request(self, url, method, payload, **headers):
        assert (url and method)

        if self.state.verbose:
            click.echo('Preparing request...')

        if not isinstance(method, str) or callable(method):
            raise ArcsecondError('Invalid HTTP request method {}. '.format(str(method)))

        # Put method name aside in its own var.
        method_name = method.upper() if isinstance(method, str) else ''

        if self.state and self.state.organisation:
            self._check_organisation_membership_and_permission(method_name, self.state.organisation)

        # Check API key, hence login state. Must do before check for org.
        headers = self._check_and_set_api_key(headers, url)
        method = getattr(requests, method.lower()) if isinstance(method, str) else method

        if payload:
            # Filtering None values out of payload.
            payload = {k: v for k, v in payload.items() if v is not None}

        return method_name, method, payload, headers

    def _build_dynamic_upload_data(self, fields, callback=None):
        encoded_data = encoder.MultipartEncoder(fields=fields)
        upload_callback = None

        if self.state.is_using_cli is True and self.state.verbose:
            bar = Bar('Uploading ' + fields['file'][0], suffix='%(percent)d%%')
            upload_callback = lambda m: bar.goto(m.bytes_read / m.len * 100)
        elif self.state.is_using_cli is False:
            upload_callback = lambda m: callback(EVENT_METHOD_PROGRESS_PERCENT, m.bytes_read / m.len * 100)

        # The monitor is the data!
        return encoder.MultipartEncoderMonitor(encoded_data, upload_callback)

    def _perform_spinner_request(self, url, method, method_name, data=None, payload=None, **headers):
        if self.state.verbose:
            click.echo('Sending {} request to {}'.format(method_name, url))
            click.echo('Payload: {}'.format(payload))

        performer = AsyncRequestPerformer(url, method, data=data, payload=payload, **headers)
        performer.start()

        spinner = Spinner()
        while performer.is_alive():
            if self.state.verbose:
                spinner.next()

        performer.join()
        response, error = performer.get_results()

        if error:
            raise error
        elif response is None:
            raise ArcsecondConnectionError(url)

        if self.state.verbose:
            click.echo()
            click.echo('Request status code ' + str(response.status_code))

        if 200 <= response.status_code < 300:
            return response.json() if response.text else {}, None
        else:
            return None, response.text

    def _check_and_set_api_key(self, headers, url):
        if API_AUTH_PATH_REGISTER in url or API_AUTH_PATH_LOGIN in url or 'Authorization' in headers.keys():
            return headers

        if self.state.verbose:
            click.echo('Checking local API key... ', nl=False)

        api_key = config_file_read_api_key(self.state.config_section())
        if not api_key:
            raise ArcsecondError('Missing API key. You must login first: $ arcsecond login')

        headers['X-Arcsecond-API-Authorization'] = 'Key ' + api_key

        if self.state.verbose:
            click.echo('OK')

        return headers

    def _check_organisation_membership_and_permission(self, method_name, organisation):
        memberships = config_file_read_organisation_memberships(self.state.config_section())
        if self.state.organisation not in memberships.keys():
            raise ArcsecondError('No membership found for organisation {}'.format(organisation))

        membership = memberships[self.state.organisation]
        if method_name not in SAFE_METHODS and membership not in WRITABLE_MEMBERSHIPS:
            raise ArcsecondError('Membership for organisation {} has no write permission'.format(organisation))
