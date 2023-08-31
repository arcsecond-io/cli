from ._base import APIEndPoint


class ObservingRunsAPIEndPoint(APIEndPoint):
    name = 'observingruns'

    def _get_list_url(self, **filters):
        return self._build_url('observingruns', **filters)

    def _get_detail_url(self, uuid):
        return self._build_url('observingruns', str(uuid))


class NightLogsAPIEndPoint(APIEndPoint):
    name = 'nightlogs'

    def _get_list_url(self, **filters):
        return self._build_url('nightlogs', **filters)

    def _get_detail_url(self, uuid):
        return self._build_url('nightlogs', str(uuid))


class ObservationsAPIEndPoint(APIEndPoint):
    name = 'observations'

    def _get_list_url(self, **filters):
        return self._build_url('observations', **filters)

    def _get_detail_url(self, uuid):
        return self._build_url('observations', str(uuid))


class CalibrationsAPIEndPoint(APIEndPoint):
    name = 'calibrations'

    def _get_list_url(self, **filters):
        return self._build_url('calibrations', **filters)

    def _get_detail_url(self, uuid):
        return self._build_url('calibrations', str(uuid))
