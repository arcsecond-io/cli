from ._base import APIEndPoint


class OrganisationsAPIEndPoint(APIEndPoint):
    name = 'organisations'

    def _get_list_url(self, **filters):
        return self._build_url('organisations', **filters)

    def _get_detail_url(self, subdomain):
        return self._build_url('organisations', subdomain)


class MembersAPIEndPoint(APIEndPoint):
    name = 'members'

    def _get_list_url(self, **filters):
        return self._build_url('members', **filters)


class OrganisationUploadKeysAPIEndPoint(APIEndPoint):
    name = 'uploadkeys'

    def _get_list_url(self, **filters):
        return self._build_url('uploadkeys', **filters)
