from ._base import APIEndPoint


class StandardStarsAPIEndPoint(APIEndPoint):
    name = 'standardstars'

    def _get_list_url(self, **filters):
        return self._build_url('standardstars', **filters)

    def _get_detail_url(self, pk):
        return self._build_url('standardstars', str(pk))


class CataloguesAPIEndPoint(APIEndPoint):
    name = 'catalogues'

    def _get_list_url(self, **filters):
        return self._build_url('catalogues', **filters)

    def _get_detail_url(self, pk):
        return self._build_url('catalogues', str(pk))
