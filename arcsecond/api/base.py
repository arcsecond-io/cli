import click
import requests

from arcsecond.config import config_file_read_api_key

class APIEndPoint(object):
    name = None


    def __init__(self, state, require_auth=False):
        self.state = state
        self.require_auth = require_auth


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
        if self.require_auth:
            headers['API-Authorization'] = config_file_read_api_key()
        return requests.get(url, headers=headers)


    def _send_post_request(self, url, payload, **headers):
        if self.require_auth:
            headers['API-Authorization'] = config_file_read_api_key()
        return requests.post(url, payload, headers=headers)


    def _echo_error(self, r):
        if self.state.debug:
            click.echo(r.text)
        else:
            json_obj = json.loads(r.text)
            click.echo(json_obj['non_field_errors'])


    def list(self):
        url = self._list_url()
        if self.state.verbose:
            click.echo('Requesting : ' + url)
        r = self._send_get_request(url)
        if r.status_code == 200:
            return r.json()
        else:
            self._echo_error(r)


    def read(self, name_or_id, **headers):
        url = self._detail_url(name_or_id)
        if self.state.verbose:
            click.echo('Requesting : ' + url)
        r = self._send_get_request(url, **headers)
        if r.status_code == 200:
            return r.json()
        else:
            self._echo_error(r)
