from ._base import APIEndPoint


class DatasetsAPIEndPoint(APIEndPoint):
    name = 'datasets'

    def _list_url(self, name=None):
        return self._root_url() + '/datasets/'

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._root_url() + '/datasets/' + uuid_str + '/'


class FITSFilesAPIEndPoint(APIEndPoint):
    name = 'fitsfiles'

    def _list_url(self, name=None):
        return self._root_url() + '/fitsfiles/'

    def _detail_url(self, pk_str):
        return self._root_url() + '/fitsfiles/' + pk_str + '/'
