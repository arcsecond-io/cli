from ._base import APIEndPoint


class SatellitesAPIEndPoint(APIEndPoint):
    name = 'satellites'

    def _get_list_url(self, **filters):
        return self._build_url('satellites', **filters)

    def _get_detail_url(self, norad_number):
        return self._build_url('satellites', norad_number)
