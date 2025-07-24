from arcsecond.errors import ArcsecondError


class UploadRemoteDatasetPreparationError(ArcsecondError):
    pass


class InvalidDatasetError(ArcsecondError):
    def __init__(self, dataset_uuid, error_string=""):
        msg = f"Invalid / unknown dataset with UUID {dataset_uuid}."
        if error_string:
            msg += f"\n{error_string}"
        super().__init__(msg)


class InvalidTelescopeError(ArcsecondError):
    def __init__(self, telescope_uuid, error_string=""):
        msg = f"Invalid / unknown telescope with UUID {telescope_uuid}."
        if error_string:
            msg += f"\n{error_string}"
        super().__init__(msg)


class InvalidTelescopeInDatasetError(ArcsecondError):
    def __init__(self, telescope_uuid, dataset_telescope_uuid, dataset_uuid):
        msg = f"Telescope {telescope_uuid} does not match with existing {dataset_telescope_uuid} in Dataset {dataset_uuid}."
        super().__init__(msg)


class InvalidOrganisationDatasetError(ArcsecondError):
    def __init__(self, dataset_uuid, org_subdomain, error_string=""):
        msg = f"Dataset with UUID {dataset_uuid} unknown within organisation {org_subdomain}."
        if error_string:
            msg += f"\n{error_string}"
        super().__init__(msg)


class InvalidOrganisationTelescopeError(ArcsecondError):
    def __init__(self, telescope_uuid, org_subdomain, error_string=""):
        msg = f"Telescope with UUID {telescope_uuid} unknown within organisation {org_subdomain}."
        if error_string:
            msg += f"\n{error_string}"
        super().__init__(msg)


class MissingTelescopeError(ArcsecondError):
    def __init__(self, dataset_uuid_or_name, error_string=""):
        msg = f"Missing Telescope for dataset with UUID/name {dataset_uuid_or_name}."
        if error_string:
            msg += f"\n{error_string}"
        super().__init__(msg)
