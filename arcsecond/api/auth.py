from .base import APIEndPoint
from .error import ArcsecondError


class AuthAPIEndPoint(APIEndPoint):
    name = 'auth'

    def authenticate(self, username, password):
        if not username:
            raise ArcsecondError("Invalid 'username' parameter {}.".format(username))
        if not password:
            raise ArcsecondError("Invalid 'password' parameter {}.".format(password))

        url = self._root_url() + '/auth/login/'
        return self._perform_request(url, 'post', {'username': username, 'password': password})

    def register(self, username, email, password1, password2):
        if not username:
            raise ArcsecondError("Missing/invalid username: {}".format(username))
        if not email or '@' not in email:
            raise ArcsecondError("Missing/invalid email: {}".format(email))
        if password1 != password2:
            raise ArcsecondError("The two passwords don't match")

        url = self._root_url() + '/auth/registration/'
        payload = {'username': username, 'email': email, 'password1': password1, 'password2': password2}
        return self._perform_request(url, 'post', payload)
