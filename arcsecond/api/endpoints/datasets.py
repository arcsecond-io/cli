from ._base import APIEndPoint


class DatasetsAPIEndPoint(APIEndPoint):
    name = 'datasets'

    def _list_url(self, **filters):
        return self._build_url('datasets', **filters)

    def _detail_url(self, uuid):
        return self._build_url('datasets', str(uuid))


class DataFilesAPIEndPoint(APIEndPoint):
    name = 'datafiles'

    def _list_url(self, **filters):
        return self._build_url('datafiles', **filters)

    def _detail_url(self, pk_str):
        return self._build_url('datafiles', pk_str)
