from ._base import APIEndPoint


class ObservingSitesAPIEndPoint(APIEndPoint):
    name = 'observingsites'

    def _list_url(self, **filters):
        return self._build_url('observingsites', **filters)

    def _detail_url(self, uuid):
        return self._build_url('observingsites', str(uuid))


class TelescopesAPIEndPoint(APIEndPoint):
    name = 'telescopes'

    def _list_url(self, **filters):
        return self._build_url('telescopes', **filters)

    def _detail_url(self, uuid):
        return self._build_url('telescopes', str(uuid))


class InstrumentsAPIEndPoint(APIEndPoint):
    name = 'instruments'

    def _list_url(self, **filters):
        return self._build_url('instruments', **filters)

    def _detail_url(self, uuid):
        return self._build_url('instruments', str(uuid))
