from ._base import APIEndPoint


class StandardStarsAPIEndPoint(APIEndPoint):
    name = 'standardstars'

    def _list_url(self, name=''):
        return self._build_url('standardstars')

    def _detail_url(self, pk):
        return self._build_url('catalogues', str(pk))
