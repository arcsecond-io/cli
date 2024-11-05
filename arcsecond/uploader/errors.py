from arcsecond.errors import ArcsecondError


class UploadRemoteFileError(ArcsecondError):
    pass


class UploadRemoteFileTagsError(ArcsecondError):
    pass


class UploadRemoteDatasetCheckError(ArcsecondError):
    pass


class InvalidUploadOptionsArcsecondError(ArcsecondError):
    def __init__(self, msg=''):
        super().__init__(f'Invalid or incomplete Upload options: {msg}')


# TODO: Check
class NotLoggedInError(ArcsecondError):
    def __init__(self):
        super().__init__('You must login first: `arcsecond login`')


class InvalidWatchOptionsError(ArcsecondError):
    def __init__(self, msg=''):
        super().__init__(f'Invalid or incomplete Watch options: {msg}')


class UnknownOrganisationError(ArcsecondError):
    def __init__(self, subdomain, error_string=''):
        msg = f'Invalid / unknown organisation with subdomain {subdomain}.'
        if error_string:
            msg += f'\n{error_string}'
        super().__init__(msg)


class InvalidAstronomerError(ArcsecondError):
    def __init__(self, username, upload_key=None, error_string=''):
        msg = f'Invalid / unknown astronomer with username "{username}"'
        if upload_key:
            msg += f' (for the provided upload_key "{upload_key}")'
        if error_string:
            msg += f'\n{error_string}'
        super().__init__(msg)


class InvalidOrgMembershipError(ArcsecondError):
    def __init__(self, subdomain, error_string=''):
        msg = f'Invalid / unknown membership for {subdomain}.'
        if error_string:
            msg += f'\n{error_string}'
        super().__init__(msg)


class InvalidOrganisationUploadKeyError(ArcsecondError):
    def __init__(self, subdomain, username, upload_key, error_string=''):
        msg = f'Invalid / unknown upload_key {upload_key} for @{username} and {subdomain} organisation.'
        if error_string:
            msg += f'\n{error_string}'
        super().__init__(msg)


class InvalidDatasetError(ArcsecondError):
    def __init__(self, dataset_uuid, error_string=''):
        msg = f'Invalid / unknown dataset with UUID {dataset_uuid}.'
        if error_string:
            msg += f'\n{error_string}'
        super().__init__(msg)


class InvalidTelescopeError(ArcsecondError):
    def __init__(self, telescope_uuid, error_string=''):
        msg = f'Invalid / unknown telescope with UUID {telescope_uuid}.'
        if error_string:
            msg += f'\n{error_string}'
        super().__init__(msg)


class InvalidTelescopeInDatasetError(ArcsecondError):
    def __init__(self, telescope_uuid, dataset_telescope_uuid, dataset_uuid):
        msg = f'Telescope {telescope_uuid} does not match with existing {dataset_telescope_uuid} in Dataset {dataset_uuid}.'
        super().__init__(msg)


class InvalidOrganisationDatasetError(ArcsecondError):
    def __init__(self, dataset_uuid, org_subdomain, error_string=''):
        msg = f'Dataset with UUID {dataset_uuid} unknown within organisation {org_subdomain}.'
        if error_string:
            msg += f'\n{error_string}'
        super().__init__(msg)


class InvalidOrganisationTelescopeError(ArcsecondError):
    def __init__(self, telescope_uuid, org_subdomain, error_string=''):
        msg = f'Telescope with UUID {telescope_uuid} unknown within organisation {org_subdomain}.'
        if error_string:
            msg += f'\n{error_string}'
        super().__init__(msg)


class MissingTelescopeError(ArcsecondError):
    def __init__(self, dataset_uuid_or_name, error_string=''):
        msg = f'Missing Telescope for dataset with UUID/name {dataset_uuid_or_name}.'
        if error_string:
            msg += f'\n{error_string}'
        super().__init__(msg)
