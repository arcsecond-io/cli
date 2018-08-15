from .base import APIEndPoint


class ProfileAPIEndPoint(APIEndPoint):
    name = 'profiles'


    def _detail_url(self, username):
        return self._root_url() + '/profiles/' + username + '/'


class PersonalProfileAPIEndPoint(ProfileAPIEndPoint):
    name = 'me'


    def __init__(self, state):
        super(PersonalProfileAPIEndPoint, self).__init__(state, True)


class ProfileAPIKeyAPIEndPoint(APIEndPoint):
    name = 'keys'


    def __init__(self, state):
        super(ProfileAPIKeyAPIEndPoint, self).__init__(state, True)


    def _detail_url(self, username):
        return self._root_url() + '/profiles/' + username + '/keys/'
