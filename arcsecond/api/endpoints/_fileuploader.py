import threading

import requests

try:
    # Python3
    from urllib.parse import urlencode
except ImportError:
    # Python2
    from urllib import urlencode

from arcsecond.api.error import (
    ArcsecondRequestTimeoutError,
    ArcsecondConnectionError,
    ArcsecondError
)


class AsyncFileUploader(object):
    """AsyncFileUploader is a helper class used when uploading files to the cloud.

    Technically speaking, it can handle any http request in a background thread.
    It is however named like this because it is returned in place of a standard
    response payload when a file is to be uploaded.
    """

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
        if self._thread.is_alive() is False:
            self._thread.start()

    def _target(self, url, method, data, payload, headers):
        try:
            self._storage['response'] = method(url, data=data, json=payload, headers=headers, timeout=60)
        except requests.Timeout:
            self._storage['error'] = ArcsecondRequestTimeoutError(url)
        except requests.exceptions.ConnectionError:
            self._storage['error'] = ArcsecondConnectionError(url)
        except Exception as e:
            self._storage['error'] = ArcsecondError(str(e))

    def finish(self):
        # I haven't found yet why self._thread can be None when target is
        # completed or close to have done so.
        if self._thread is not None:
            self._thread.join()
        return self.get_results()

    def is_alive(self):
        return False if self._thread is None else self._thread.is_alive()

    def get_results(self):
        response = self._storage.get('response', None)
        if isinstance(response, dict):
            # Responses of standard JSON payload requests are dict
            return response
        elif response is not None:
            if 200 <= response.status_code < 300:
                return response.json() if response.text else {}, None
            else:
                return None, response.text
        else:
            return None, self._storage.get('error', None)
