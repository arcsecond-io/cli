from ._base import APIEndPoint


class FindingChartsAPIEndPoint(APIEndPoint):
    name = 'findingcharts'

    def _get_list_url(self, **filters):
        name = filters.get('name') or ''
        return self._build_url('findingcharts', name)
