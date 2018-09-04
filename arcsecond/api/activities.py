from .base import APIEndPoint


class ActivitiesAPIEndPoint(APIEndPoint):
    name = 'activities'

    def _list_url(self):
        return self._root_url() + '/activities/'

    def _detail_url(self, pk):
        return self._root_url() + '/activities/' + pk + '/'

    def _open_url(self, name):
        # Yes, in the web, the url is unified with objects.
        return self._root_open_url() + '/live/'
