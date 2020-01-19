from arcsecond import Arcsecond
from tests.utils import save_test_credentials, clear_test_credentials


def test_default_empty_state():
    clear_test_credentials()
    assert Arcsecond.is_logged_in(debug=True) is False
    assert Arcsecond.username(debug=True) == ''
    assert Arcsecond.memberships(debug=True) == {}


def test_default_logged_in_state():
    save_test_credentials('cedric')
    assert Arcsecond.is_logged_in(debug=True) is True
    assert Arcsecond.username(debug=True) == 'cedric'
    assert Arcsecond.memberships(debug=True) == {}


def test_default_logged_in_with_membership_state():
    save_test_credentials('cedric', {'saao': 'superadmin'})
    assert Arcsecond.is_logged_in(debug=True) is True
    assert Arcsecond.username(debug=True) == 'cedric'
    assert Arcsecond.memberships(debug=True) == {'saao': 'superadmin'}
