from arcsecond import ArcsecondConfig
from arcsecond.options import State
from tests.utils import clear_test_credentials, save_test_credentials


def test_default_empty_state():
    clear_test_credentials()
    assert ArcsecondConfig(State(api_name='test')).is_logged_in is False
    assert ArcsecondConfig(State(api_name='test')).username == ''
    assert ArcsecondConfig(State(api_name='test')).memberships == {}


def test_default_logged_in_state():
    clear_test_credentials()
    save_test_credentials('cedric')
    assert ArcsecondConfig(State(api_name='test')).is_logged_in is True
    assert ArcsecondConfig(State(api_name='test')).username == 'cedric'
    assert ArcsecondConfig(State(api_name='test')).memberships == {}


def test_default_logged_in_with_membership_state():
    clear_test_credentials()
    save_test_credentials('cedric', [{'organisation': 'saao', 'role': 'superadmin'}])
    assert ArcsecondConfig(State(api_name='test')).is_logged_in is True
    assert ArcsecondConfig(State(api_name='test')).username == 'cedric'
    assert ArcsecondConfig(State(api_name='test')).memberships == {'saao': 'superadmin'}
