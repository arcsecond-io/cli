from ._base import APIEndPoint


class ActivitiesAPIEndPoint(APIEndPoint):
    name = 'activities'

    def _list_url(self, **filters):
        return self._build_url('activities', **filters)

    def _detail_url(self, pk):
        return self._build_url('activities', str(pk))

    def _open_url(self, name):
        return self._root_open_url() + '/live/'
