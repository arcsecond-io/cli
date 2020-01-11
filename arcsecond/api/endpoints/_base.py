import threading
import uuid
import os

import click
import requests
from progress.spinner import Spinner

from arcsecond.api.constants import (
    ARCSECOND_API_URL_DEV,
    ARCSECOND_API_URL_PROD,
    ARCSECOND_WWW_URL_DEV,
    ARCSECOND_WWW_URL_PROD,
    API_AUTH_PATH_LOGIN,
    API_AUTH_PATH_REGISTER)

from arcsecond.api.error import ArcsecondConnectionError, ArcsecondError
from arcsecond.api.helpers import make_file_upload_payload
from arcsecond.config import config_file_read_api_key, config_file_read_organisation_memberships
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

    def _async_perform_request(self, url, method, payload=None, files=None, **headers):
        def _async_perform_request_store_response(storage, method, url, payload, files, headers):
            try:
                storage['response'] = method(url, json=payload, files=files, headers=headers)
            except requests.exceptions.ConnectionError:
                storage['error'] = ArcsecondConnectionError(self._get_base_url())
            except Exception as e:
                storage['error'] = ArcsecondError(str(e))

        storage = {}
        thread = threading.Thread(target=_async_perform_request_store_response,
                                  args=(storage, method, url, payload, files, headers))
        thread.start()

        spinner = Spinner()
        while thread.is_alive():
            if self.state.verbose:
                spinner.next()
        thread.join()
        if self.state.verbose:
            click.echo()

        if 'error' in storage.keys():
            raise storage.get('error')

        return storage.get('response', None)

    def _prepare_request(self, url, method, payload, **headers):
        assert (url and method)

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

        return url, method_name, method, payload, headers

    def _perform_request(self, url, method, payload, callback=None, **headers):
        url, method_name, method, payload, headers = self._prepare_request(url, method, payload, **headers)

        if self.state.verbose:
            click.echo('Sending {} request to {}'.format(method_name, url))
            click.echo('Payload: {}'.format(payload))

        payload, files = self._extract_files_from_payload(payload)
        response = method(url, json=payload, files=files, headers=headers)

        if response is None:
            raise ArcsecondConnectionError(url)

        if self.state.verbose:
            click.echo('Request status code ' + str(response.status_code))

        if 200 <= response.status_code < 300:
            return response.json() if response.text else {}, None
        else:
            return None, response.text

    def list(self, name='', **headers):
        return self._perform_request(self._list_url(name), 'get', None, **headers)

    def create(self, payload, **headers):
        payload = self._check_for_file_in_payload(payload)
        return self._perform_request(self._list_url(), 'post', payload, **headers)

    def read(self, id_name_uuid, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'get', None, **headers)

    def update(self, id_name_uuid, payload, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'put', payload, **headers)

    def delete(self, id_name_uuid, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'delete', None, **headers)
