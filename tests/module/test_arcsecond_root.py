from arcsecond import ArcsecondAPI
from tests.utils import save_test_credentials, clear_test_credentials


def test_default_empty_state():
    clear_test_credentials()
    assert ArcsecondAPI.is_logged_in(debug=True) is False
    assert ArcsecondAPI.username(debug=True) == ''
    assert ArcsecondAPI.memberships(debug=True) == {}


def test_default_logged_in_state():
    save_test_credentials('cedric')
    assert ArcsecondAPI.is_logged_in(debug=True) is True
    assert ArcsecondAPI.username(debug=True) == 'cedric'
    assert ArcsecondAPI.memberships(debug=True) == {}


def test_default_logged_in_with_membership_state():
    save_test_credentials('cedric', {'saao': 'superadmin'})
    assert ArcsecondAPI.is_logged_in(debug=True) is True
    assert ArcsecondAPI.username(debug=True) == 'cedric'
    assert ArcsecondAPI.memberships(debug=True) == {'saao': 'superadmin'}
