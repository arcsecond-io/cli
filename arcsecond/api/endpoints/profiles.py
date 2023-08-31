from ._base import APIEndPoint


class ProfileAPIEndPoint(APIEndPoint):
    name = 'profiles'

    def _get_list_url(self, **filters):
        return self._build_url('profiles', **filters)

    def _get_detail_url(self, username):
        return self._build_url('profiles', username)


class PersonalProfileAPIEndPoint(ProfileAPIEndPoint):
    name = 'me'


class ProfileAPIKeyAPIEndPoint(APIEndPoint):
    name = 'apikey'

    def _get_detail_url(self, username):
        return self._build_url('profiles', username, 'apikey')


class ProfileUploadKeyAPIEndPoint(APIEndPoint):
    name = 'uploadkey'

    def _get_detail_url(self, username):
        return self._build_url('profiles', username, 'uploadkey')


class ProfileSharedKeysAPIEndPoint(APIEndPoint):
    name = 'sharedkeys'

    def _get_list_url(self, username):
        return self._build_url('profiles', username, 'sharedkeys')

    # No detail URL for now
    # def _get_detail_url(self, username):
    #     return self._build_url('profiles', username, 'sharedkeys')
