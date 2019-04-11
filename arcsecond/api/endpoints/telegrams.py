from ._base import APIEndPoint


class TelegramsATelAPIEndPoint(APIEndPoint):
    name = 'telegrams_atel'

    def _list_url(self, name=''):
        return self._build_url('telegrams', 'ATel')

    def _detail_url(self, identifier):
        return self._build_url('telegrams', 'ATel', identifier)
