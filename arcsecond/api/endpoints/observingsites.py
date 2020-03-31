from ._base import APIEndPoint


class ObservingSitesAPIEndPoint(APIEndPoint):
    name = 'observingsites'

    def _list_url(self, **filters):
        return self._build_url('observingsites', **filters)

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._build_url('observingsites', uuid_str)


class TelescopesAPIEndPoint(APIEndPoint):
    name = 'telescopes'

    def _list_url(self, **filters):
        return self._build_url('telescopes', **filters)

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._build_url('telescopes', uuid_str)


class InstrumentsAPIEndPoint(APIEndPoint):
    name = 'instruments'

    def _list_url(self, **filters):
        return self._build_url('instruments', **filters)

    def _detail_url(self, uuid_str):
        self._check_uuid(uuid_str)
        return self._build_url('instruments', uuid_str)
