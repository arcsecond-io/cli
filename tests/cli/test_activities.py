import json
import uuid

import httpretty
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.api.constants import ARCSECOND_API_URL_DEV
from arcsecond.api.error import ArcsecondInputValueError
from tests.utils import register_successful_login


@httpretty.activate
def test_activities_with_valid_coordinates():
    runner = CliRunner()
    register_successful_login(runner)
    site_uuid = str(uuid.uuid4())
    coords_ra = 2.33
    coords_dec = 4.55

    def request_callback(request, uri, response_headers):
        data = json.loads(request.body)
        assert data.get('observing_site') == site_uuid
        assert data.get('coordinates') == {'right_ascension': coords_ra, 'declination': coords_dec}
        return [200, response_headers, json.dumps({"result": "OK"})]

    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + '/activities/',
        body=request_callback
    )

    coords = "{},{}".format(coords_ra, coords_dec)
    result = runner.invoke(cli.activities, ['create', '--observing_site', site_uuid, '--coordinates', coords, '-d'])
    assert result.exit_code == 0 and not result.exception


@httpretty.activate
def test_activities_with_invalid_coordinates():
    runner = CliRunner()
    register_successful_login(runner)
    site_uuid = str(uuid.uuid4())
    coords_ra = 2.33
    coords_dec = 4.55
    coords = "{}$$${}".format(coords_ra, coords_dec)
    result = runner.invoke(cli.activities, ['create', '--observing_site', site_uuid, '--coordinates', coords, '-d'])
    assert result.exit_code != 0
    assert isinstance(result.exception, ArcsecondInputValueError)


@httpretty.activate
def test_activities_with_invalid_coordinates2():
    runner = CliRunner()
    register_successful_login(runner)
    site_uuid = str(uuid.uuid4())
    coords_ra = 2.33
    coords_dec = 4.55
    coords = "{},{},{}".format(coords_ra, coords_dec, coords_dec)
    result = runner.invoke(cli.activities, ['create', '--observing_site', site_uuid, '--coordinates', coords, '-d'])
    assert result.exit_code != 0
    assert isinstance(result.exception, ArcsecondInputValueError)


@httpretty.activate
def test_activities_with_invalid_coordinates3():
    runner = CliRunner()
    register_successful_login(runner)
    site_uuid = str(uuid.uuid4())
    coords_ra = 2.33
    coords = "yoyo,{}".format(coords_ra)
    result = runner.invoke(cli.activities, ['create', '--observing_site', site_uuid, '--coordinates', coords, '-d'])
    assert result.exit_code != 0
    assert isinstance(result.exception, ArcsecondInputValueError)
