from ._base import APIEndPoint


class ObservingRunsAPIEndPoint(APIEndPoint):
    name = 'observingruns'

    def _list_url(self, **filters):
        return self._build_url('observingruns', **filters)

    def _detail_url(self, uuid):
        return self._build_url('observingruns', str(uuid))


class NightLogsAPIEndPoint(APIEndPoint):
    name = 'nightlogs'

    def _list_url(self, **filters):
        return self._build_url('nightlogs', **filters)

    def _detail_url(self, uuid):
        return self._build_url('nightlogs', str(uuid))


class ObservationsAPIEndPoint(APIEndPoint):
    name = 'observations'

    def _list_url(self, **filters):
        return self._build_url('observations', **filters)

    def _detail_url(self, uuid):
        return self._build_url('observations', str(uuid))


class CalibrationsAPIEndPoint(APIEndPoint):
    name = 'calibrations'

    def _list_url(self, **filters):
        return self._build_url('calibrations', **filters)

    def _detail_url(self, uuid):
        return self._build_url('calibrations', str(uuid))


class FindingChartsAPIEndPoint(APIEndPoint):
    name = 'findingcharts'

    def _list_url(self, **filters):
        name = filters.get('name') or ''
        return self._build_url('findingcharts', name)
