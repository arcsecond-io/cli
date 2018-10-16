import threading
import uuid

import click
import requests
from progress.spinner import Spinner

from arcsecond.config import config_file_read_api_key
from arcsecond.options import State
from arcsecond.api.error import ArcsecondError, ArcsecondConnectionError
from arcsecond.api.constants import (ARCSECOND_API_URL_PROD,
                                     ARCSECOND_API_URL_DEV,
                                     ARCSECOND_WWW_URL_PROD,
                                     ARCSECOND_WWW_URL_DEV)


class APIEndPoint(object):
    name = None

    def __init__(self, state=None, prefix=''):
        self.state = state or State()
        self.prefix = prefix
        if len(prefix) and prefix[0] != '/':
            self.prefix = '/' + self.prefix

    def _base_url(self):
        return ARCSECOND_API_URL_DEV if self.state.debug else ARCSECOND_API_URL_PROD

    def _root_url(self):
        return self._base_url() + self.prefix

    def _root_open_url(self):
        if hasattr(self.state, 'open'):
            return ARCSECOND_WWW_URL_DEV if self.state.debug is True else ARCSECOND_WWW_URL_PROD

    def _list_url(self, name=None):
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
        if 'login' in url or 'register' in url or 'Authorization' in headers.keys():
            return headers

        if self.state.verbose:
            click.echo('Checking local API key... ', nl=False)

        api_key = config_file_read_api_key(self.state.debug)
        if not api_key:
            raise ArcsecondError('Missing API key. You must login first: $ arcsecond login')

        headers['X-Arcsecond-API-Authorization'] = 'Key ' + api_key

        if self.state.verbose:
            click.echo('OK')
        return headers

    def _async_perform_request(self, url, method, payload=None, files=None, **headers):
        def _async_perform_request_store_response(storage, method, url, payload, files, headers):
            try:
                storage['response'] = method(url, data=payload, files=files, headers=headers)
            except requests.exceptions.ConnectionError:
                storage['error'] = ArcsecondConnectionError(self._base_url())
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

    def _perform_request(self, url, method, payload, **headers):
        assert (url and method)

        if not isinstance(method, str) or callable(method):
            raise ArcsecondError('Invalid HTTP request method {}. '.format(str(method)))

        headers = self._check_and_set_api_key(headers, url)

        method_name = method.upper() if isinstance(method, str) else ''
        method = getattr(requests, method.lower()) if isinstance(method, str) else method
        files = payload.pop('files', None) if payload else None

        if self.state.verbose:
            click.echo('Sending {} request to {}'.format(method_name, url))

        response = self._async_perform_request(url, method, payload, files, **headers)

        if response is None:
            raise ArcsecondConnectionError(url)

        if self.state.verbose:
            click.echo('Request status code ' + str(response.status_code))

        if response.status_code >= 200 and response.status_code < 300:
            return (response.json() if response.text else {}, None)
        else:
            return (None, response.text)

    def list(self, name=None, **headers):
        return self._perform_request(self._list_url(name), 'get', None, **headers)

    def create(self, payload, **headers):
        return self._perform_request(self._list_url(), 'post', payload, **headers)

    def read(self, id_name_uuid, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'get', None, **headers)

    def update(self, id_name_uuid, payload, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'put', payload, **headers)

    def delete(self, id_name_uuid, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'delete', None, **headers)
