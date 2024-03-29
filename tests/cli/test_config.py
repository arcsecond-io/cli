from arcsecond import ArcsecondConfig
from arcsecond.options import State

SECTION = 'test'
USERNAME = 'cedric'
ACCESS_KEY = '1-2-3'
UPLOAD_KEY = '9-8-7'


def test_config_file_path():
    assert str(ArcsecondConfig.file_path()).endswith('arcsecond/config.ini')


def test_config_file_is_logged_in_no_file():
    config = ArcsecondConfig(State(api_name='test'))
    config.reset()
    assert config.is_logged_in is False


def test_config_api_server():
    config = ArcsecondConfig(State(api_name='test'))
    assert config.api_server == ''
    config.api_server = 'http://localhost/dummy:8989'
    assert config.api_server == 'http://localhost/dummy:8989'


def test_config_memberships():
    config = ArcsecondConfig(State(api_name='test'))
    assert config.memberships == {}
    ms = [{'organisation': 'oma', 'role': 'superadmin'}, {'organisation': 'arcsecond', 'role': 'member'}]
    config.save_memberships(ms)
    assert config.memberships == {'oma': 'superadmin', 'arcsecond': 'member'}


def test_config_access_key():
    config = ArcsecondConfig(State(api_name='test'))
    assert config.access_key == ''
    config.save_access_key('1234')
    assert config.access_key == '1234'


def test_config_upload_key():
    config = ArcsecondConfig(State(api_name='test'))
    assert config.upload_key == ''
    config.save_upload_key('1234')
    assert config.upload_key == '1234'
