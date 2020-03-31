from ._base import APIEndPoint


class StandardStarsAPIEndPoint(APIEndPoint):
    name = 'standardstars'

    def _list_url(self, **filters):
        return self._build_url('standardstars', **filters)

    def _detail_url(self, pk):
        return self._build_url('standardstars', str(pk))


class CataloguesAPIEndPoint(APIEndPoint):
    name = 'catalogues'

    def _list_url(self, **filters):
        return self._build_url('catalogues', **filters)

    def _detail_url(self, pk):
        return self._build_url('catalogues', str(pk))
