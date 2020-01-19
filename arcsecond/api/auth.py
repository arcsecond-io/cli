from .endpoints._base import APIEndPoint
from .error import ArcsecondError
from .constants import API_AUTH_PATH_LOGIN, API_AUTH_PATH_REGISTER


class AuthAPIEndPoint(APIEndPoint):
    name = 'auth'

    def login(self, username, password):
        if not username:
            raise ArcsecondError("Invalid 'username' parameter {}.".format(username))
        if not password:
            raise ArcsecondError("Invalid 'password' parameter {}.".format(password))

        url = self._root_url() + API_AUTH_PATH_LOGIN
        return self._perform_request(url, 'post', {'username': username, 'password': password})

    def register(self, username, email, password1, password2):
        if not username:
            raise ArcsecondError("Missing/invalid username: {}".format(username))
        if not email or '@' not in email:
            raise ArcsecondError("Missing/invalid email: {}".format(email))
        if password1 != password2:
            raise ArcsecondError("The two passwords don't match")

        msg = 'By registering, you confirm agreeing with Terms & Conditions (https://www.arcsecond.io/terms) [y/N]:'
        terms_agreement = input(msg)

        if terms_agreement.lower() not in ['y', 'Y', 'yes', 'YES']:
            raise ArcsecondError("Agreement to Terms and Conditions not accepted. Aborting registration.")

        url = self._root_url() + API_AUTH_PATH_REGISTER
        payload = {'username': username, 'email': email, 'password1': password1, 'password2': password2}
        return self._perform_request(url, 'post', payload)
