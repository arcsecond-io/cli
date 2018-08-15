from .base import APIEndPoint


class AuthAPIEndPoint(APIEndPoint):
    name = 'auth'


    def authenticate(self, username, password):
        url = self._root_url() + '/auth/login/'
        r = self._send_post_request(url, {'username': username, 'password': password})
        if r.status_code == 200:
            return r.json()
        else:
            self._echo_error(r)


class APIKeyAPIEndPoint(APIEndPoint):
    name = 'keys'


    def __init__(self, state):
        super(APIKeyAPIEndPoint, self).__init__(state, True)


    def _detail_url(self, username):
        return self._root_url() + '/profiles/' + username + '/keys/'
