from .base import APIEndPoint


class ObjectsAPIEndPoint(APIEndPoint):
    name = 'objects'

    def _detail_url(self, name):
        return self._root_url() + '/objects/' + name + '/'

    def _open_url(self, name):
        return self._root_open_url() + '/objects/' + name


class ExoplanetsAPIEndPoint(APIEndPoint):
    name = 'exoplanets'

    def _list_url(self, name=None):
        return self._root_url() + '/exoplanets/'

    def _detail_url(self, name):
        return self._list_url() + name + '/'

    def _open_url(self, name):
        # Yes, in the web, the url is unified with objects.
        return self._root_open_url() + '/objects/' + name
