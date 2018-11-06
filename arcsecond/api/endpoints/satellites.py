from ._base import APIEndPoint


class SatellitesAPIEndPoint(APIEndPoint):
    name = 'satellites'

    def _list_url(self, name=''):
        return self._build_url('satellites')

    def _detail_url(self, norad_number):
        return self._build_url('satellites', norad_number)
