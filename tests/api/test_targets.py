from unittest.mock import Mock, patch

from arcsecond import ArcsecondAPI
from arcsecond.api.config import ArcsecondConfig
from arcsecond.api.endpoint import ArcsecondAPIEndpoint
from arcsecond.api.resources import ArcsecondTargetListsResource


def make_config():
    config = Mock(spec=ArcsecondConfig)
    config.api_server = "https://fixture.example.io"
    config.verbose = False
    config.access_key = "test_access_key"
    config.upload_key = None
    return config


def test_api_exposes_targets_and_targetlists():
    api = ArcsecondAPI(make_config(), subdomain="demo")
    assert isinstance(api.targets, ArcsecondAPIEndpoint)
    assert isinstance(api.targetlists, ArcsecondTargetListsResource)


@patch("httpx.post")
def test_targets_create_accepts_keyword_fields(mock_post):
    config = make_config()
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"uuid": "target-1"}
    mock_response.text = '{"uuid": "target-1"}'
    mock_post.return_value = mock_response

    response, error = ArcsecondAPIEndpoint(config, "targets", "demo").create(
        name="NGC 104",
        ra_deg=6.023625,
        dec_deg=-72.08128,
        source_name="47 Tuc",
    )

    assert error is None
    assert response == {"uuid": "target-1"}
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {
        "name": "NGC 104",
        "ra_deg": 6.023625,
        "dec_deg": -72.08128,
        "source_name": "47 Tuc",
    }


@patch("httpx.get")
@patch("httpx.patch")
def test_targets_upsert_updates_existing_match(mock_patch, mock_get):
    config = make_config()

    mock_list_response = Mock()
    mock_list_response.status_code = 200
    mock_list_response.json.return_value = {"results": [{"uuid": "target-1", "name": "M42"}]}
    mock_list_response.text = '{"results": [{"uuid": "target-1", "name": "M42"}]}'
    mock_get.return_value = mock_list_response

    mock_patch_response = Mock()
    mock_patch_response.status_code = 200
    mock_patch_response.json.return_value = {"uuid": "target-1", "name": "M42"}
    mock_patch_response.text = '{"uuid": "target-1", "name": "M42"}'
    mock_patch.return_value = mock_patch_response

    response, error = ArcsecondAPIEndpoint(config, "targets", "demo").upsert(
        name="M42", ra_deg=83.82208, dec_deg=-5.39111
    )

    assert error is None
    assert response == {"uuid": "target-1", "name": "M42"}
    patch_args, patch_kwargs = mock_patch.call_args
    assert patch_args[0] == "https://fixture.example.io/demo/targets/target-1/"
    assert patch_kwargs["json"] == {
        "name": "M42",
        "ra_deg": 83.82208,
        "dec_deg": -5.39111,
    }


@patch("httpx.post")
@patch("httpx.get")
def test_targets_upsert_creates_missing_match(mock_get, mock_post):
    config = make_config()

    mock_list_response = Mock()
    mock_list_response.status_code = 200
    mock_list_response.json.return_value = {"results": []}
    mock_list_response.text = '{"results": []}'
    mock_get.return_value = mock_list_response

    mock_post_response = Mock()
    mock_post_response.status_code = 201
    mock_post_response.json.return_value = {"uuid": "target-2", "name": "M31"}
    mock_post_response.text = '{"uuid": "target-2", "name": "M31"}'
    mock_post.return_value = mock_post_response

    response, error = ArcsecondAPIEndpoint(config, "targets", "demo").upsert(
        name="M31", ra_deg=10.6847083, dec_deg=41.26875
    )

    assert error is None
    assert response == {"uuid": "target-2", "name": "M31"}
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {
        "name": "M31",
        "ra_deg": 10.6847083,
        "dec_deg": 41.26875,
    }


@patch("httpx.post")
def test_targetlists_create_accepts_targets(mock_post):
    config = make_config()
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"uuid": "list-1"}
    mock_response.text = '{"uuid": "list-1"}'
    mock_post.return_value = mock_response

    response, error = ArcsecondTargetListsResource(
        config, "targetlists", "demo"
    ).create(
        name="Tonight",
        description="Best objects",
        targets=[
            {"name": "M 42", "target_class": "AstronomicalObject"},
            {
                "id": 8,
                "name": "51 Peg b",
                "target_class": "Exoplanet",
                "is_free": False,
            },
        ],
    )

    assert error is None
    assert response == {"uuid": "list-1"}
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {
        "name": "Tonight",
        "description": "Best objects",
        "targets": [
            {"name": "M 42", "target_class": "AstronomicalObject"},
            {"id": 8, "name": "51 Peg b", "target_class": "Exoplanet"},
        ],
    }


@patch("httpx.get")
@patch("httpx.patch")
def test_targetlists_add_targets_merges_existing_targets(mock_patch, mock_get):
    config = make_config()

    mock_read_response = Mock()
    mock_read_response.status_code = 200
    mock_read_response.json.return_value = {
        "uuid": "list-1",
        "targets": [
            {"id": 1, "name": "M 42", "target_class": "AstronomicalObject"},
            {"id": 2, "name": "51 Peg b", "target_class": "Exoplanet"},
        ],
    }
    mock_read_response.text = (
        '{"uuid": "list-1", "targets": [{"id": 1, "name": "M 42", "target_class": "AstronomicalObject"}, '
        '{"id": 2, "name": "51 Peg b", "target_class": "Exoplanet"}]}'
    )
    mock_get.return_value = mock_read_response

    mock_patch_response = Mock()
    mock_patch_response.status_code = 200
    mock_patch_response.json.return_value = {"uuid": "list-1"}
    mock_patch_response.text = '{"uuid": "list-1"}'
    mock_patch.return_value = mock_patch_response

    response, error = ArcsecondTargetListsResource(
        config, "targetlists", "demo"
    ).add_targets(
        "list-1",
        [
            {"id": 2, "name": "51 Peg b", "target_class": "Exoplanet"},
            {"name": "M 31", "target_class": "AstronomicalObject"},
        ],
    )

    assert error is None
    assert response == {"uuid": "list-1"}
    _, kwargs = mock_patch.call_args
    assert kwargs["json"] == {
        "targets": [
            {"id": 1, "name": "M 42", "target_class": "AstronomicalObject"},
            {"id": 2, "name": "51 Peg b", "target_class": "Exoplanet"},
            {"name": "M 31", "target_class": "AstronomicalObject"},
        ]
    }


@patch("httpx.get")
@patch("httpx.patch")
def test_targetlists_remove_targets_uses_target_payloads(mock_patch, mock_get):
    config = make_config()

    mock_read_response = Mock()
    mock_read_response.status_code = 200
    mock_read_response.json.return_value = {
        "uuid": "list-1",
        "targets": [
            {"id": 1, "name": "M 42", "target_class": "AstronomicalObject"},
            {"id": 2, "name": "51 Peg b", "target_class": "Exoplanet"},
            {"name": "M 31", "target_class": "AstronomicalObject"},
        ],
    }
    mock_read_response.text = (
        '{"uuid": "list-1", "targets": [{"id": 1, "name": "M 42", "target_class": "AstronomicalObject"}, '
        '{"id": 2, "name": "51 Peg b", "target_class": "Exoplanet"}, '
        '{"name": "M 31", "target_class": "AstronomicalObject"}]}'
    )
    mock_get.return_value = mock_read_response

    mock_patch_response = Mock()
    mock_patch_response.status_code = 200
    mock_patch_response.json.return_value = {"uuid": "list-1"}
    mock_patch_response.text = '{"uuid": "list-1"}'
    mock_patch.return_value = mock_patch_response

    response, error = ArcsecondTargetListsResource(
        config, "targetlists", "demo"
    ).remove_targets(
        "list-1",
        [{"id": 2, "name": "51 Peg b", "target_class": "Exoplanet"}],
    )

    assert error is None
    assert response == {"uuid": "list-1"}
    _, kwargs = mock_patch.call_args
    assert kwargs["json"] == {
        "targets": [
            {"id": 1, "name": "M 42", "target_class": "AstronomicalObject"},
            {"name": "M 31", "target_class": "AstronomicalObject"},
        ]
    }
