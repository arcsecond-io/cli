from arcsecond.errors import ArcsecondError


class InvalidCameraError(ArcsecondError):
    def __init__(self, camera_uuid, message):
        super().__init__(f"Invalid camera UUID {camera_uuid}: {message}")


class InvalidOrganisationCameraError(ArcsecondError):
    def __init__(self, camera_uuid, org_subdomain, message):
        super().__init__(f"Invalid camera UUID {camera_uuid} for organisation {org_subdomain}: {message}")
