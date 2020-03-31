from ._base import APIEndPoint


class ObservingRunsAPIEndPoint(APIEndPoint):
    name = 'observingruns'

    def _list_url(self, **filters):
        return self._build_url('observingruns', **filters)

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._build_url('observingruns', uuid_str)


class NightLogAPIEndPoint(APIEndPoint):
    name = 'nightlogs'

    def _list_url(self, **filters):
        return self._build_url('nightlogs', **filters)

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._build_url('nightlogs', uuid_str)
