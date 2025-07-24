from arcsecond.errors import ArcsecondError


class InvalidCameraError(ArcsecondError):
    def __init__(self, camera_uuid, message):
        super().__init__(f"Invalid camera UUID {camera_uuid}: {message}")


class InvalidOrganisationCameraError(ArcsecondError):
    def __init__(self, camera_uuid, org_subdomain, message):
        super().__init__(
            f"Invalid camera UUID {camera_uuid} for organisation {org_subdomain}: {message}"
        )


class MissingTimestampError(ArcsecondError):
    def __init__(self, filename):
        msg = f"Missing UTC timestamp for camera image {filename}."
        super().__init__(msg)
