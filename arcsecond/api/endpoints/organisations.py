from ._base import APIEndPoint


class OrganisationsAPIEndPoint(APIEndPoint):
    name = 'organisations'

    def _list_url(self, **filters):
        return self._build_url('organisations', **filters)

    def _detail_url(self, subdomain):
        return self._build_url('organisations', subdomain)
