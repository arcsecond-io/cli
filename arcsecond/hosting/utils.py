import base64
import os
import secrets
from pathlib import Path


def _read_env_value(key, env_path=None):
    """Read a single value from a KEY=value / KEY="value" .env file.

    Returns None if the file or key is missing. Mirrors the parsing
    shape used by _parse_env_keys in hosting/local.py.
    """
    path = Path(env_path) if env_path else Path.cwd() / ".env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        if k.strip() != key:
            continue
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        return v
    return None


def _get_random_secret_key():
    # No '%' to avoid interpolation surprises
    chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$^&*(-_=+)"
    return "".join(secrets.choice(chars) for _ in range(50))


def _get_encryption_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode("UTF8")


def _get_random_postgres_password():
    """Generate a strong, shell- and URL-safe Postgres password.

    Uses URL-safe base64 (``[A-Za-z0-9_-]``) so the value never needs
    quoting in the .env file or any future connection string. 32 random
    bytes → 43 chars, ~256 bits of entropy. Trailing '=' padding is
    stripped because it triggers shell parsing weirdness in some setups.
    """
    return base64.urlsafe_b64encode(os.urandom(32)).decode("UTF8").rstrip("=")
