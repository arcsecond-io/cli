import base64
import os
import secrets
import subprocess
from pathlib import Path


def _container_running(name):
    try:
        out = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


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
    # The value lands unquoted in .env, which Compose interpolates: '$name'
    # would be swallowed (with a "variable is not set" warning) and '%' is
    # unsafe in configparser-style readers. Neither belongs in the alphabet.
    chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#^&*(-_=+)"
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


def _replace_env_value(text, key, new_value):
    """Return `text` with `key`'s value replaced, preserving line order.

    Only the first assignment is rewritten, matching how docker compose reads
    the file. Returns None when the key is absent, so the caller can refuse
    rather than silently appending a second one.
    """
    out = []
    replaced = False
    for line in text.splitlines():
        stripped = line.strip()
        if (
            not replaced
            and stripped
            and not stripped.startswith("#")
            and "=" in stripped
            and stripped.split("=", 1)[0].strip() == key
        ):
            out.append(f"{key}={new_value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        return None
    return "\n".join(out) + "\n"


def _set_env_value(env_path, key, value):
    """Set `key` in a .env file: rewrite it in place if present, append it
    otherwise. Creates the file when there is none."""
    path = Path(env_path)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = _replace_env_value(text, key, value)
    if updated is None:
        if text and not text.endswith("\n"):
            text += "\n"
        updated = text + f"{key}={value}\n"
    path.write_text(updated, encoding="utf-8")
