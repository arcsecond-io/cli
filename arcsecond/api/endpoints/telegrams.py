from ._base import APIEndPoint


class TelegramsATelAPIEndPoint(APIEndPoint):
    name = 'telegrams_atel'

    def _get_list_url(self, **filters):
        return self._build_url('telegrams', 'ATel')

    def _get_detail_url(self, identifier):
        return self._build_url('telegrams', 'ATel', identifier)
