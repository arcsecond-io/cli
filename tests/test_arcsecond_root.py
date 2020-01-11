from arcsecond import Arcsecond
from .utils import save_test_credentials, clear_test_credentials


def test_default_empty_state():
    clear_test_credentials()
    assert Arcsecond.is_logged_in(test=True) is False
    assert Arcsecond.username(test=True) == ''
    assert Arcsecond.memberships(test=True) == {}


def test_default_logged_in_state():
    save_test_credentials('cedric')
    assert Arcsecond.is_logged_in(test=True) is True
    assert Arcsecond.username(test=True) == 'cedric'
    assert Arcsecond.memberships(test=True) == {}


def test_default_logged_in_with_membership_state():
    save_test_credentials('cedric', {'saao': 'superadmin'})
    assert Arcsecond.is_logged_in(test=True) is True
    assert Arcsecond.username(test=True) == 'cedric'
    assert Arcsecond.memberships(test=True) == {'saao': 'superadmin'}
