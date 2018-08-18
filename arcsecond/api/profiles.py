from .base import APIEndPoint


class ProfileAPIEndPoint(APIEndPoint):
    name = 'profiles'

    def _detail_url(self, username):
        return self._root_url() + '/profiles/' + username + '/'


class PersonalProfileAPIEndPoint(ProfileAPIEndPoint):
    name = 'me'


class ProfileAPIKeyAPIEndPoint(APIEndPoint):
    name = 'keys'

    def _detail_url(self, username):
        return self._root_url() + '/profiles/' + username + '/keys/'
