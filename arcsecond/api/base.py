import threading
import uuid

import click
import requests
from progress.spinner import Spinner

from arcsecond.config import config_file_read_api_key
from .error import ArcsecondError


class APIEndPoint(object):
    name = None

    def __init__(self, state):
        self.state = state

    def _root_url(self):
        return 'http://localhost:8000' if self.state.debug is True else 'https://api.arcsecond.io'

    def _root_open_url(self):
        if hasattr(self.state, 'open'):
            return 'http://localhost:8080' if self.state.debug is True else 'https://www.arcsecond.io'

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

    def _check_and_set_api_key(self, headers, url=''):
        if self.state.verbose:
            click.echo('Checking local API key... ', nl=False)
        api_key = config_file_read_api_key(self.state.debug)
        if not api_key and not ('login' in url or 'Authorization' in headers.keys()):
            raise ArcsecondError('Missing API key. You must login first: $ arcsecond login')
        headers['X-Arcsecond-API-Authorization'] = 'Key ' + api_key
        if self.state.verbose:
            click.echo('OK')
        return headers

    def _perform_request(self, url, method, payload=None, **headers):
        if not isinstance(method, str) or callable(method):
            raise ArcsecondError('Invalid HTTP request method {}. '.format(str(method)))

        method = getattr(requests, method.lower()) if isinstance(method, str) else method
        headers = self._check_and_set_api_key(headers, url or '')
        if self.state.verbose:
            click.echo('Sending request to ' + url)

        def _async_perform_requests(storage, method, url, payload, headers):
            storage['response'] = method(url, data=payload, headers=headers)

        storage = {}
        thread = threading.Thread(target=_async_perform_requests, args=(storage, method, url, payload, headers))
        thread.start()

        spinner = Spinner()
        while thread.is_alive():
            if self.state.verbose:
                spinner.next()
        thread.join()
        if self.state.verbose:
            click.echo()

        response = storage['response']
        if self.state.verbose:
            click.echo('Request status code ' + str(response.status_code))

        if response.status_code >= 200 and response.status_code < 300:
            return (response.json(), None)
        else:
            return (None, response.text)

    def list(self, name=None):
        return self._perform_request(self._list_url(name), 'get')

    def create(self, payload):
        return self._perform_request(self._list_url(), 'post', payload)

    def read(self, id_name_uuid, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'get', **headers)

    def update(self, id_name_uuid, payload, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'put', payload, **headers)

    def delete(self, id_name_uuid, **headers):
        return self._perform_request(self._detail_url(id_name_uuid), 'delete', **headers)
