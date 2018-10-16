from ._base import APIEndPoint


class SatellitesAPIEndPoint(APIEndPoint):
    name = 'satellites'

    def _list_url(self, name=None):
        return self._root_url() + '/satellites/'

    def _detail_url(self, norad_number):
        return self._root_url() + '/satellites/' + norad_number + '/'
