import click
import requests

from arcsecond.config import config_file_read_api_key
from .error import ArcsecondError


class APIEndPoint(object):
    name = None

    def __init__(self, state):
        self.state = state

    def _root_url(self):
        return 'http://api.lvh.me:8000' if self.state.debug is True else 'https://api.arcsecond.io'

    def _root_open_url(self):
        if hasattr(self.state, 'open'):
            return 'http://localhost:8080' if self.state.debug is True else 'https://www.arcsecond.io'

    def _list_url(self):
        raise Exception('You must override this method.')

    def _detail_url(self, name_or_id):
        raise Exception('You must override this method.')

    def _open_url(self, name_or_id):
        raise Exception('You must override this method.')

    def _check_and_set_api_key(self, headers, url=''):
        if self.state.verbose:
            click.echo('Checking local API key.')
        api_key = config_file_read_api_key(self.state.debug)
        if not api_key and not ('login' in url or 'Authorization' in headers.keys()):
            raise ArcsecondError('Missing API key. You must login first: $ arcsecond login')
        headers['X-Arcsecond-API-Authorization'] = 'Key ' + api_key
        return headers

    def _perform_request(self, url, method, payload=None, **headers):
        if not isinstance(method, str) or callable(method):
            raise ArcsecondError('Invalid HTTP request method {}. '.format(str(method)))
        method = getattr(requests, method.lower()) if isinstance(method, str) else method
        headers = self._check_and_set_api_key(headers, url or '')
        if self.state.verbose:
            click.echo('Requesting : ' + url)
        r = method(url, data=payload, headers=headers)
        if r.status_code >= 200 and r.status_code < 300:
            return (r.json(), None)
        else:
            return (None, r.text)

    def list(self):
        return self._perform_request(self._list_url(), 'get')

    def create(self, payload):
        return self._perform_request(self._list_url(), 'post', payload)

    def read(self, name_or_id, **headers):
        return self._perform_request(self._detail_url(name_or_id), 'get', **headers)

    def update(self, name_or_id, payload, **headers):
        return self._perform_request(self._detail_url(name_or_id), 'put', payload, **headers)

    def delete(self, name_or_id, **headers):
        return self._perform_request(self._detail_url(name_or_id), 'delete', **headers)
