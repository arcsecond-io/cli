from .base import APIEndPoint


class FindingChartsAPIEndPoint(APIEndPoint):
    name = 'finding charts'


    def __init__(self, state):
        super(FindingChartsAPIEndPoint, self).__init__(state, False)


    def _detail_url(self, name):
        return self._root_url() + '/findingcharts/' + name
