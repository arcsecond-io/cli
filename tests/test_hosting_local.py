from pathlib import Path

from arcsecond.hosting import local


def test_write_env_file_includes_jwt_signing_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(local, "_get_random_secret_key", lambda: "test-secret")
    monkeypatch.setattr(local, "_get_encryption_key", lambda: "test-encryption")
    monkeypatch.setattr(local, "_get_random_postgres_password", lambda: "test-pg-password")
    monkeypatch.setattr(local, "prompt_shared_data_path", lambda: "/tmp/shared-data")

    local.write_env_file()

    env_contents = (Path(tmp_path) / ".env").read_text(encoding="utf-8")
    assert "SECRET_KEY=test-secret" in env_contents
    assert "AUTH_JWT_SIGNING_KEY=test-secret" in env_contents
    assert "AGENT_JWT_SIGNING_KEY=test-secret" in env_contents
    assert "FIELD_ENCRYPTION_KEY=test-encryption" in env_contents
    assert 'SHARED_DATA_PATH="/tmp/shared-data"' in env_contents
    # Fresh installs get a per-install random password, never the historical default.
    assert "POSTGRES_PASSWORD=test-pg-password" in env_contents
    assert "POSTGRES_PASSWORD=arcsecond_docker" not in env_contents


def test_write_env_file_generates_strong_password_on_fresh_install(tmp_path, monkeypatch):
    """End-to-end: when the helper is not stubbed, the generated value
    actually has the entropy / character set we expect."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(local, "_get_random_secret_key", lambda: "x")
    monkeypatch.setattr(local, "_get_encryption_key", lambda: "x")
    monkeypatch.setattr(local, "prompt_shared_data_path", lambda: "/tmp/p")

    local.write_env_file()

    env_contents = (Path(tmp_path) / ".env").read_text(encoding="utf-8")
    pg_line = next(line for line in env_contents.splitlines() if line.startswith("POSTGRES_PASSWORD="))
    pg_password = pg_line.split("=", 1)[1]
    assert pg_password != "arcsecond_docker"
    assert len(pg_password) >= 32, f"too weak: {pg_password!r}"
    # URL-safe base64 alphabet: never needs quoting in shells or connection strings.
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    assert set(pg_password) <= allowed


def test_write_env_file_preserves_existing_values_and_adds_missing(tmp_path, monkeypatch):
    """Critical for upgrades: rewriting POSTGRES_PASSWORD in .env after
    Postgres has been initialized would lock the operator out — the live
    DB still uses the original password baked in at first boot. Existing
    keys must never be touched."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(local, "_get_random_secret_key", lambda: "generated-secret")
    monkeypatch.setattr(local, "_get_encryption_key", lambda: "generated-encryption")
    monkeypatch.setattr(local, "_get_random_postgres_password", lambda: "freshly-generated-but-unused")
    monkeypatch.setattr(local, "prompt_shared_data_path", lambda: "/tmp/generated-shared")

    env_path = Path(tmp_path) / ".env"
    env_path.write_text(
        "\n".join(
            [
                "SECRET_KEY=existing-secret",
                "POSTGRES_USER=existing-user",
                "POSTGRES_PASSWORD=existing-pg-password",
                "",
            ]
        ),
        encoding="utf-8",
    )

    local.write_env_file()
    env_contents = env_path.read_text(encoding="utf-8")

    assert "SECRET_KEY=existing-secret" in env_contents
    assert "POSTGRES_USER=existing-user" in env_contents
    # The pre-existing Postgres password is preserved verbatim — never overwritten.
    assert "POSTGRES_PASSWORD=existing-pg-password" in env_contents
    assert "POSTGRES_PASSWORD=freshly-generated-but-unused" not in env_contents
    assert "AUTH_JWT_SIGNING_KEY=generated-secret" in env_contents
    assert "AGENT_JWT_SIGNING_KEY=generated-secret" in env_contents
    assert "FIELD_ENCRYPTION_KEY=generated-encryption" in env_contents
    assert 'SHARED_DATA_PATH="/tmp/generated-shared"' in env_contents
    assert "POSTGRES_DB=arcsecond_docker" in env_contents


def test_write_docker_compose_file_keeps_existing_and_writes_latest_when_different(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    local.write_docker_compose_file()

    compose_path = Path(tmp_path) / "docker-compose.yml"
    original_generated = compose_path.read_text(encoding="utf-8")

    compose_path.write_text("custom-compose-content\n", encoding="utf-8")
    local.write_docker_compose_file()

    latest_path = Path(tmp_path) / "docker-compose.latest.yml"
    assert compose_path.read_text(encoding="utf-8") == "custom-compose-content\n"
    assert latest_path.exists()
    assert latest_path.read_text(encoding="utf-8") == original_generated
