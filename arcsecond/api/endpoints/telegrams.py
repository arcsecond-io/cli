from ._base import APIEndPoint


class TelegramsATelAPIEndPoint(APIEndPoint):
    name = 'telegrams_atel'

    def _list_url(self, name=None):
        return self._root_url() + '/telegrams/ATel/'

    def _detail_url(self, identifier):
        return self._list_url() + identifier + '/'
