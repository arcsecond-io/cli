from .base import APIEndPoint


class FindingChartsAPIEndPoint(APIEndPoint):
    name = 'finding charts'
    def _list_url(self, name=None):
        return self._root_url() + '/findingcharts/' + (name + '/' if name else '')
