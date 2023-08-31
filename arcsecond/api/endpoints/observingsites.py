from ._base import APIEndPoint


class ObservingSitesAPIEndPoint(APIEndPoint):
    name = 'observingsites'

    def _get_list_url(self, **filters):
        return self._build_url('observingsites', **filters)

    def _get_detail_url(self, uuid):
        return self._build_url('observingsites', str(uuid))


class TelescopesAPIEndPoint(APIEndPoint):
    name = 'telescopes'

    def _get_list_url(self, **filters):
        return self._build_url('telescopes', **filters)

    def _get_detail_url(self, uuid):
        return self._build_url('telescopes', str(uuid))


class InstrumentsAPIEndPoint(APIEndPoint):
    name = 'instruments'

    def _get_list_url(self, **filters):
        return self._build_url('instruments', **filters)

    def _get_detail_url(self, uuid):
        return self._build_url('instruments', str(uuid))
