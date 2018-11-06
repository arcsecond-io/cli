from ._base import APIEndPoint


class ProfileAPIEndPoint(APIEndPoint):
    name = 'profiles'

    def _list_url(self, name=''):
        return self._build_url('profiles')

    def _detail_url(self, username):
        return self._build_url('profiles', username)


class PersonalProfileAPIEndPoint(ProfileAPIEndPoint):
    name = 'me'


class ProfileAPIKeyAPIEndPoint(APIEndPoint):
    name = 'keys'

    def _detail_url(self, username):
        return self._build_url('profiles', username, 'keys')
