from ._base import APIEndPoint


class ObservingRunsAPIEndPoint(APIEndPoint):
    name = 'observingruns'

    def _list_url(self, name=''):
        return self._build_url('observingruns')

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._build_url('observingruns', uuid_str)


class NightLogAPIEndPoint(APIEndPoint):
    name = 'nightlogs'

    def _list_url(self, name=''):
        return self._build_url('nightlogs')

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._build_url('nightlogs', uuid_str)
