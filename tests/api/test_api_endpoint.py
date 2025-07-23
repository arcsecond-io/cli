from unittest.mock import Mock, patch

import pytest

from arcsecond.api.config import ArcsecondConfig
from arcsecond.api.endpoint import ArcsecondAPIEndpoint, ArcsecondError


@pytest.fixture
def config():
    config = Mock(spec=ArcsecondConfig)
    config.api_server = "https://fixture.example.io"
    config.verbose = False
    config.access_key = "test_access_key"
    config.upload_key = None
    return config


@pytest.fixture
def endpoint(config):
    return ArcsecondAPIEndpoint(config=config, path="test", subdomain="sub")


def test_init(config):
    endpoint = ArcsecondAPIEndpoint(config=config, path="test", subdomain="sub")
    assert endpoint.path == "test"


def test_get_base_url(config):
    config.api_server = "https://text.example.io/"
    endpoint = ArcsecondAPIEndpoint(config=config, path="test", subdomain="sub")

    # Test with URL already ending with slash
    assert endpoint._get_base_url() == "https://text.example.io/"


def test_build_url(endpoint):
    # Test basic URL building
    url = endpoint._build_url("resource")
    assert url == "https://fixture.example.io/sub/resource/"

    # Test with filters
    url = endpoint._build_url("resource", page=1, limit=10)
    assert url == "https://fixture.example.io/sub/resource/?page=1&limit=10"


def test_list_url(endpoint):
    # Test without filters
    url = endpoint._list_url()
    assert url == "https://fixture.example.io/sub/test/"

    # Test with filters
    url = endpoint._list_url(page=1)
    assert url == "https://fixture.example.io/sub/test/?page=1"


def test_detail_url(endpoint):
    url = endpoint._detail_url("123")
    assert url == "https://fixture.example.io/sub/test/123/"


@patch("httpx.get")
def test_list_success(mock_get, endpoint):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_response.text = '{"results": []}'
    mock_get.return_value = mock_response

    response, error = endpoint.list()
    assert error is None
    assert response == {"results": []}
    mock_get.assert_called_once()


@patch("httpx.get")
def test_read_success(mock_get, endpoint):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "123"}
    mock_response.text = '{"id": "123"}'
    mock_get.return_value = mock_response

    response, error = endpoint.read("123")
    assert error is None
    assert response == {"id": "123"}


@patch("httpx.post")
def test_create_success(mock_post, endpoint):
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "new"}
    mock_response.text = '{"id": "new"}'
    mock_post.return_value = mock_response

    response, error = endpoint.create(json={"name": "test"})
    assert error is None
    assert response == {"id": "new"}


@patch("httpx.patch")
def test_update_success(mock_patch, endpoint):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "123", "updated": True}
    mock_response.text = '{"id": "123", "updated": True}'
    mock_patch.return_value = mock_response

    response, error = endpoint.update("123", json={"name": "updated"})
    assert error is None
    assert response == {"id": "123", "updated": True}


@patch("httpx.delete")
def test_delete_success(mock_delete, endpoint):
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.text = ""
    mock_delete.return_value = mock_response

    response, error = endpoint.delete("123")
    assert error is None
    assert response == {}


def test_check_and_set_auth_key_no_key(config):
    config.access_key = None
    endpoint = ArcsecondAPIEndpoint(config=config, path="test")

    with pytest.raises(ArcsecondError) as exc_info:
        endpoint._check_and_set_auth_key({}, "https://fixture.example.io/test")
    assert "Missing auth keys" in str(exc_info.value)


@patch("httpx.get")
def test_error_response(mock_get, endpoint):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_get.return_value = mock_response

    response, error = endpoint.read("123")
    assert response is None
    assert isinstance(error, ArcsecondError)
