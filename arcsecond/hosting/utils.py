import base64
import os
import secrets


def _get_random_secret_key():
    # No '%' to avoid interpolation surprises
    chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$^&*(-_=+)"
    return "".join(secrets.choice(chars) for _ in range(50))


def _get_encryption_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode('UTF8')


def _get_random_postgres_password():
    """Generate a strong, shell- and URL-safe Postgres password.

    Uses URL-safe base64 (``[A-Za-z0-9_-]``) so the value never needs
    quoting in the .env file or any future connection string. 32 random
    bytes → 43 chars, ~256 bits of entropy. Trailing '=' padding is
    stripped because it triggers shell parsing weirdness in some setups.
    """
    return base64.urlsafe_b64encode(os.urandom(32)).decode('UTF8').rstrip('=')
