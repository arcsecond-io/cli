from unittest.mock import MagicMock, patch

import pytest

from arcsecond.cloud.uploader.allskycameraimages.context import (
    AllSkyCameraImageUploadContext,
)
from arcsecond.cloud.uploader.allskycameraimages.errors import (
    InvalidCameraError,
    InvalidOrganisationCameraError,
)
from tests.utils import random_string


@pytest.fixture
def mock_config():
    """Create a mock ArcsecondConfig."""
    config = MagicMock()
    config.username = "test_user"
    config.upload_key = "test_key"
    config.api_name = random_string()
    config.api_server = "http://mock.example.com"
    config.access_key = None  # very important, because access_key takes precedence on upload_key in headers setting.
    config.upload_key = "1234567890"
    return config


@pytest.fixture
def mock_api_endpoint():
    with patch("arcsecond.api.ArcsecondAPIEndpoint") as mock:
        yield mock


def test_init_with_valid_camera_uuid(mock_config):
    """Test initialization with valid camera UUID"""
    context = AllSkyCameraImageUploadContext(
        config=mock_config, input_camera_uuid="test-uuid-123"
    )
    assert context._input_camera_uuid == "test-uuid-123"
    assert context._camera is None


def test_init_with_none_camera_uuid(mock_config):
    """Test initialization with None camera UUID"""
    context = AllSkyCameraImageUploadContext(config=mock_config, input_camera_uuid=None)
    assert context._input_camera_uuid is None
    assert context._camera is None


def test_validate_context_specific_with_valid_uuid(mock_config, mock_api_endpoint):
    """Test _validate_context_specific with valid UUID"""
    with patch("arcsecond.api.endpoint.ArcsecondAPIEndpoint.read") as mock_func_read:
        context = AllSkyCameraImageUploadContext(
            config=mock_config, input_camera_uuid="test-uuid-123"
        )
        mock_func_read.return_value = (
            {"uuid": "test-uuid-123", "name": "test-camera"},
            None,
        )
        context._validate_context_specific()
        mock_func_read.assert_called_once()
        assert context._camera == {"uuid": "test-uuid-123", "name": "test-camera"}


def test_validate_context_specific_without_uuid(mock_config):
    """Test _validate_context_specific without UUID"""
    context = AllSkyCameraImageUploadContext(config=mock_config, input_camera_uuid=None)
    with pytest.raises(ValueError, match="Camera UUID is required for image uploads"):
        context._validate_context_specific()


def test_validate_input_camera_uuid_with_error(mock_config, mock_api_endpoint):
    """Test _validate_input_camera_uuid with error response"""
    with patch("arcsecond.api.endpoint.ArcsecondAPIEndpoint.read") as mock_func_read:
        mock_func_read.return_value = (None, "Camera not found")

        context = AllSkyCameraImageUploadContext(
            config=mock_config, input_camera_uuid="invalid-uuid"
        )

        with pytest.raises(InvalidCameraError):
            context._validate_input_camera_uuid()


def test_validate_input_camera_uuid_with_org_error(mock_config, mock_api_endpoint):
    """Test _validate_input_camera_uuid with organization error"""
    with patch("arcsecond.api.endpoint.ArcsecondAPIEndpoint.read") as mock_func_read:
        mock_func_read.return_value = (None, "Camera not found")

        context = AllSkyCameraImageUploadContext(
            config=mock_config,
            input_camera_uuid="invalid-uuid",
            org_subdomain="test-org",
        )

        with pytest.raises(InvalidOrganisationCameraError):
            context._validate_input_camera_uuid()


def test_camera_properties(mock_config):
    """Test camera-related properties"""
    context = AllSkyCameraImageUploadContext(
        config=mock_config, input_camera_uuid="test-uuid-123"
    )

    # Test before camera data is set
    assert context.camera_uuid == "test-uuid-123"
    assert context.camera_name == ""
    assert context.camera is None

    # Test after camera data is set
    context._camera = {"uuid": "test-uuid-123", "name": "test-camera"}
    assert context.camera_uuid == "test-uuid-123"
    assert context.camera_name == "test-camera"
    assert context.camera == {"uuid": "test-uuid-123", "name": "test-camera"}
