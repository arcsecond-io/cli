import base64
import os
import secrets


def _get_random_secret_key():
    # No '%' to avoid interpolation surprises
    chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$^&*(-_=+)"
    return "".join(secrets.choice(chars) for _ in range(50))


def _get_encryption_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode('UTF8')
