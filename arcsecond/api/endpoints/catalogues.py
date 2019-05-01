from ._base import APIEndPoint


class CataloguesAPIEndPoint(APIEndPoint):
    name = 'catalogues'

    def _list_url(self, name=''):
        return self._build_url('catalogues')

    def _detail_url(self, pk):
        return self._build_url('catalogues', str(pk))
