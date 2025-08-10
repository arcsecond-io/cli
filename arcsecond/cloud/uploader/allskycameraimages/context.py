import click

from arcsecond.api import ArcsecondAPIEndpoint
from arcsecond.cloud.uploader.context import BaseUploadContext

from .errors import InvalidCameraError, InvalidOrganisationCameraError


class AllSkyCameraImageUploadContext(BaseUploadContext):
    """Upload context for all-sky camera image uploads"""

    def __init__(
        self,
        config,
        input_camera_uuid,
        org_subdomain=None,
        custom_tags=None,
    ):
        super().__init__(config, org_subdomain, custom_tags)
        self._input_camera_uuid = str(input_camera_uuid) if input_camera_uuid else None
        self._camera = None

    @property
    def upload_api_endpoint(self):
        return ArcsecondAPIEndpoint(
            self.config,
            f"allskycameras/{self._input_camera_uuid}/images",
            self.subdomain,
        )

    def _validate_context_specific(self):
        """Run validations specific to image uploads"""
        if self._input_camera_uuid:
            self._validate_input_camera_uuid()
        else:
            raise ValueError("Camera UUID is required for image uploads")

    def _validate_input_camera_uuid(self):
        """Validate the camera UUID exists"""
        click.echo(f" • Looking for a camera with UUID {self._input_camera_uuid}...")
        endpoint = ArcsecondAPIEndpoint(self.config, "allskycameras", self.subdomain)
        self._camera, error = endpoint.read(self._input_camera_uuid)

        if error is not None:
            if self._subdomain:
                raise InvalidOrganisationCameraError(
                    self._input_camera_uuid, self._subdomain, str(error)
                )
            else:
                raise InvalidCameraError(str(self._input_camera_uuid), str(error))

    @property
    def camera_uuid(self):
        return self._camera.get("uuid", "") if self._camera else self._input_camera_uuid

    @property
    def camera_name(self):
        return self._camera.get("name", "") if self._camera else ""

    @property
    def camera(self):
        return self._camera if self._camera else None
