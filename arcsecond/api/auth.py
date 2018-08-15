from .base import APIEndPoint


class AuthAPIEndPoint(APIEndPoint):
    name = 'auth'


    def authenticate(self, username, password):
        url = self._root_url() + '/auth/login/'
        r = self._send_post_request(url, {'username': username, 'password': password})
        if r.status_code >= 200 and r.status_code < 300:
            return (r.json(), None)
        else:
            return (None, r.json())
