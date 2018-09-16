from .base import APIEndPoint


class ObservingSitesAPIEndPoint(APIEndPoint):
    name = 'observingsites'

    def _list_url(self, name=None):
        return self._root_url() + '/observingsites/'

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._root_url() + '/observingsites/' + uuid_str + '/'


class TelescopesAPIEndPoint(APIEndPoint):
    name = 'telescopes'

    def _list_url(self, name=None):
        return self._root_url() + '/telescopes/'

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._root_url() + '/telescopes/' + uuid_str + '/'


class InstrumentsAPIEndPoint(APIEndPoint):
    name = 'instruments'

    def _list_url(self, name=None):
        return self._root_url() + '/instruments/'

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._root_url() + '/instruments/' + uuid_str + '/'
