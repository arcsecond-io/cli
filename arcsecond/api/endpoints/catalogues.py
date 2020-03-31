from ._base import APIEndPoint


class CataloguesAPIEndPoint(APIEndPoint):
    name = 'catalogues'

    def _list_url(self, **filters):
        return self._build_url('catalogues', **filters)

    def _detail_url(self, pk):
        return self._build_url('catalogues', str(pk))
