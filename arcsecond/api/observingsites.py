from .base import APIEndPoint


class ObservingSitesAPIEndPoint(APIEndPoint):
    def _list_url(self, name=None):
        return self._root_url() + '/observingsites/'

    def _detail_url(self, uuid):
        return self._root_url() + '/observingsites/' + uuid + '/'


class InstrumentsAPIEndPoint(APIEndPoint):
    def _list_url(self, name=None):
        return self._root_url() + '/instruments/'

    def _detail_url(self, uuid):
        return self._root_url() + '/instruments/' + uuid + '/'
