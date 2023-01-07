from arcsecond import ArcsecondAPI
from tests.utils import clear_test_credentials, save_test_credentials


def test_default_empty_state():
    clear_test_credentials()
    assert ArcsecondAPI.is_logged_in(api='test') is False
    assert ArcsecondAPI.username(api='test') == ''
    assert ArcsecondAPI.memberships(api='test') == {}


def test_default_logged_in_state():
    clear_test_credentials()
    save_test_credentials('cedric')
    assert ArcsecondAPI.is_logged_in(api='test') is True
    assert ArcsecondAPI.username(api='test') == 'cedric'
    assert ArcsecondAPI.memberships(api='test') == {}


def test_default_logged_in_with_membership_state():
    clear_test_credentials()
    save_test_credentials('cedric', {'saao': 'superadmin'})
    assert ArcsecondAPI.is_logged_in(api='test') is True
    assert ArcsecondAPI.username(api='test') == 'cedric'
    assert ArcsecondAPI.memberships(api='test') == {'saao': 'superadmin'}
