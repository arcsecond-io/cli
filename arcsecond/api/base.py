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

    def _send_get_request(self, url, **headers):
        key = config_file_read_api_key(self.state.debug)
        if 'Authorization' not in headers.keys():
            if not key:
                raise ArcsecondError('Missing API key. You must login first: $ arcsecond login')
            headers['X-Arcsecond-API-Authorization'] = 'Key ' + key
        return requests.get(url, headers=headers)

    def _send_post_request(self, url, payload, **headers):
        key = config_file_read_api_key(self.state.debug)
        if 'login' not in url:
            if not key and 'login' not in url:
                raise ArcsecondError('Missing API key. You must login first: $ arcsecond login')
            headers['X-Arcsecond-API-Authorization'] = 'Key ' + key
        return requests.post(url, payload, headers=headers)

    def list(self):
        url = self._list_url()
        if self.state.verbose:
            click.echo('Requesting : ' + url)
        r = self._send_get_request(url)
        if r.status_code >= 200 and r.status_code < 300:
            return (r.json(), None)
        else:
            return (None, r.text)

    def read(self, name_or_id, **headers):
        url = self._detail_url(name_or_id)
        if self.state.verbose:
            click.echo('Requesting : ' + url)
        r = self._send_get_request(url, **headers)
        if r.status_code >= 200 and r.status_code < 300:
            return (r.json(), None)
        else:
            return (None, r.text)
