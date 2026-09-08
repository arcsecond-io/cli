from arcsecond.hosting.utils import _get_random_secret_key


def test_secret_key_has_no_compose_interpolation_characters():
    # Compose interpolates '$name' inside .env; '%' trips configparser readers.
    for _ in range(200):
        key = _get_random_secret_key()
        assert len(key) == 50
        assert "$" not in key
        assert "%" not in key
