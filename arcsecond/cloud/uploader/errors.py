from arcsecond.errors import ArcsecondError


class UploadRemoteFileError(ArcsecondError):
    pass


class UploadRemoteFileInvalidatedContextError(ArcsecondError):
    def __init__(self, msg=''):
        super().__init__(f'The UploadContext must be validated first. Call `context.validate()`.')


class UploadRemoteFileMetadataError(ArcsecondError):
    pass


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
