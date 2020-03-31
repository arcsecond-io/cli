from ._base import APIEndPoint


class ObjectsAPIEndPoint(APIEndPoint):
    name = 'objects'

    def _detail_url(self, name):
        return self._build_url('objects', name)

    def _open_url(self, name):
        return self._root_open_url() + '/objects/' + name


class ExoplanetsAPIEndPoint(APIEndPoint):
    name = 'exoplanets'

    def _list_url(self, **filters):
        return self._build_url('exoplanets', **filters)

    def _detail_url(self, name):
        return self._build_url('exoplanets', name)

    def _open_url(self, name):
        # Yes, in the web, the url is unified with /objects/.
        return self._root_open_url() + '/objects/' + name
