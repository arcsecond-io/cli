from importlib import resources
from pathlib import Path

from click.testing import CliRunner

from arcsecond.hosting import local


def _stub_env_generators(monkeypatch):
    monkeypatch.setattr(local, "_get_random_secret_key", lambda: "test-secret")
    monkeypatch.setattr(local, "_get_encryption_key", lambda: "test-encryption")
    monkeypatch.setattr(
        local, "_get_random_postgres_password", lambda: "test-pg-password"
    )
    monkeypatch.setattr(local, "prompt_shared_data_path", lambda: "/tmp/shared-data")


def _packaged_compose_text():
    return (
        resources.files("arcsecond.hosting.docker")
        .joinpath("docker-compose.yml")
        .read_text(encoding="utf-8")
    )


def test_write_env_file_includes_jwt_signing_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(local, "_get_random_secret_key", lambda: "test-secret")
    monkeypatch.setattr(local, "_get_encryption_key", lambda: "test-encryption")
    monkeypatch.setattr(
        local, "_get_random_postgres_password", lambda: "test-pg-password"
    )
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


def test_write_env_file_generates_strong_password_on_fresh_install(
    tmp_path, monkeypatch
):
    """End-to-end: when the helper is not stubbed, the generated value
    actually has the entropy / character set we expect."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(local, "_get_random_secret_key", lambda: "x")
    monkeypatch.setattr(local, "_get_encryption_key", lambda: "x")
    monkeypatch.setattr(local, "prompt_shared_data_path", lambda: "/tmp/p")

    local.write_env_file()

    env_contents = (Path(tmp_path) / ".env").read_text(encoding="utf-8")
    pg_line = next(
        line
        for line in env_contents.splitlines()
        if line.startswith("POSTGRES_PASSWORD=")
    )
    pg_password = pg_line.split("=", 1)[1]
    assert pg_password != "arcsecond_docker"
    assert len(pg_password) >= 32, f"too weak: {pg_password!r}"
    # URL-safe base64 alphabet: never needs quoting in shells or connection strings.
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    assert set(pg_password) <= allowed


def test_write_env_file_preserves_existing_values_and_adds_missing(
    tmp_path, monkeypatch
):
    """Critical for upgrades: rewriting POSTGRES_PASSWORD in .env after
    Postgres has been initialized would lock the operator out — the live
    DB still uses the original password baked in at first boot. Existing
    keys must never be touched."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(local, "_get_random_secret_key", lambda: "generated-secret")
    monkeypatch.setattr(local, "_get_encryption_key", lambda: "generated-encryption")
    monkeypatch.setattr(
        local, "_get_random_postgres_password", lambda: "freshly-generated-but-unused"
    )
    monkeypatch.setattr(
        local, "prompt_shared_data_path", lambda: "/tmp/generated-shared"
    )

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


def test_write_docker_compose_file_keeps_existing_and_writes_latest_when_different(
    tmp_path, monkeypatch
):
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


def test_write_env_file_adds_gcn_placeholder_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stub_env_generators(monkeypatch)

    local.write_env_file()

    env_contents = (Path(tmp_path) / ".env").read_text(encoding="utf-8")
    assert "GCN_CONSUMER_CLIENT_ID=\n" in env_contents
    assert "GCN_CONSUMER_CLIENT_SECRET=\n" in env_contents
    assert local.GCN_ENV_COMMENT in env_contents


def test_write_env_file_backfills_gcn_keys_into_existing_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stub_env_generators(monkeypatch)

    local.write_env_file()
    env_path = Path(tmp_path) / ".env"
    before = env_path.read_text(encoding="utf-8")
    pruned = "\n".join(
        line
        for line in before.splitlines()
        if not line.startswith("GCN_") and line != local.GCN_ENV_COMMENT
    )
    env_path.write_text(pruned + "\n", encoding="utf-8")

    local.write_env_file()
    after = env_path.read_text(encoding="utf-8")
    assert "GCN_CONSUMER_CLIENT_ID=" in after
    assert "GCN_CONSUMER_CLIENT_SECRET=" in after
    assert local.GCN_ENV_COMMENT in after
    assert "SECRET_KEY=test-secret" in after


def test_write_env_file_does_not_prompt_when_nothing_is_missing(tmp_path, monkeypatch):
    """The SHARED_DATA_PATH prompt used to fire on every re-run because the
    value dict was built eagerly. Values must now be computed lazily."""
    monkeypatch.chdir(tmp_path)
    _stub_env_generators(monkeypatch)
    local.write_env_file()

    def explode():
        raise AssertionError("prompt fired although .env is complete")

    monkeypatch.setattr(local, "prompt_shared_data_path", explode)
    local.write_env_file()


def test_compose_fresh_write_with_alerts_contains_the_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    local.write_docker_compose_file(enabled_services={"alerts"})

    text = (Path(tmp_path) / "docker-compose.yml").read_text(encoding="utf-8")
    assert text == _packaged_compose_text()
    assert "# >>> arcsecond:alerts" in text
    assert "container_name: arcsecond-alerts" in text
    assert text.index("arcsecond-alerts") < text.index("\nvolumes:")


def test_compose_fresh_write_without_alerts_strips_the_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    local.write_docker_compose_file()

    text = (Path(tmp_path) / "docker-compose.yml").read_text(encoding="utf-8")
    assert "arcsecond:alerts" not in text
    assert "arcsecond-alerts" not in text
    assert "\n\n\n" not in text  # the blank separator went with the block


def test_strip_then_splice_roundtrips_the_packaged_file():
    packaged = _packaged_compose_text()
    stripped = local._strip_optional_service_block(packaged, "alerts")
    respliced = local._splice_optional_service_block(stripped, packaged, "alerts")
    assert respliced == packaged


def test_compose_splices_alerts_into_a_previously_declined_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    local.write_docker_compose_file()  # declined: no alerts block

    local.write_docker_compose_file(enabled_services={"alerts"})

    compose_path = Path(tmp_path) / "docker-compose.yml"
    assert compose_path.read_text(encoding="utf-8") == _packaged_compose_text()
    # The splice made the file equal to the expected content: no .latest.yml.
    assert not (Path(tmp_path) / "docker-compose.latest.yml").exists()


def test_compose_splice_preserves_customizations_and_is_idempotent(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    local.write_docker_compose_file()
    compose_path = Path(tmp_path) / "docker-compose.yml"
    customized = "# my local note\n" + compose_path.read_text(encoding="utf-8")
    compose_path.write_text(customized, encoding="utf-8")

    local.write_docker_compose_file(enabled_services={"alerts"})
    local.write_docker_compose_file(enabled_services={"alerts"})

    text = compose_path.read_text(encoding="utf-8")
    assert text.startswith("# my local note\n")
    assert text.count("# >>> arcsecond:alerts") == 1
    # Still customized, so the packaged copy lands beside it.
    assert (Path(tmp_path) / "docker-compose.latest.yml").exists()


def test_compose_upgrade_from_prior_version_converges_with_alerts(
    tmp_path, monkeypatch
):
    """A pristine older-version file must converge to the packaged one —
    header included — instead of collecting .latest.yml on every run."""
    monkeypatch.chdir(tmp_path)
    packaged = _packaged_compose_text()
    old = local._strip_optional_service_block(packaged, "alerts").replace(
        f"# Version {local._compose_version(packaged)}", "# Version 6.2"
    )
    compose_path = Path(tmp_path) / "docker-compose.yml"
    compose_path.write_text(old, encoding="utf-8")

    local.write_docker_compose_file(enabled_services={"alerts"})

    assert compose_path.read_text(encoding="utf-8") == packaged
    assert not (Path(tmp_path) / "docker-compose.latest.yml").exists()


def test_compose_upgrade_from_prior_version_converges_when_declined(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    packaged = _packaged_compose_text()
    expected = local._strip_optional_service_block(packaged, "alerts")
    old = expected.replace(
        f"# Version {local._compose_version(packaged)}", "# Version 6.2"
    )
    compose_path = Path(tmp_path) / "docker-compose.yml"
    compose_path.write_text(old, encoding="utf-8")

    local.write_docker_compose_file()

    assert compose_path.read_text(encoding="utf-8") == expected
    assert not (Path(tmp_path) / "docker-compose.latest.yml").exists()


def test_compose_explicit_removal_strips_the_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    local.write_docker_compose_file(enabled_services={"alerts"})

    local.write_docker_compose_file(removed_services={"alerts"})

    text = (Path(tmp_path) / "docker-compose.yml").read_text(encoding="utf-8")
    assert "arcsecond:alerts" not in text
    assert not (Path(tmp_path) / "docker-compose.latest.yml").exists()


def test_compose_without_volumes_anchor_falls_back_to_latest(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    compose_path = Path(tmp_path) / "docker-compose.yml"
    compose_path.write_text("custom-compose-content\n", encoding="utf-8")

    local.write_docker_compose_file(enabled_services={"alerts"})

    assert compose_path.read_text(encoding="utf-8") == "custom-compose-content\n"
    assert (Path(tmp_path) / "docker-compose.latest.yml").exists()
    out = capsys.readouterr().out
    assert "volumes:" in out and "alerts" in out


def test_optional_service_decisions_roundtrip(tmp_path):
    env_path = tmp_path / ".env"
    local._record_optional_service_decision(env_path, "alerts", True)
    assert local._read_optional_service_decisions(env_path) == {"alerts": True}

    local._record_optional_service_decision(env_path, "alerts", False)
    assert local._read_optional_service_decisions(env_path) == {"alerts": False}
    contents = env_path.read_text(encoding="utf-8")
    assert contents.count(local.OPTIONAL_SERVICES_ENV_KEY) == 1


def test_optional_service_decisions_preserve_unknown_tokens(tmp_path):
    """A newer CLI may have recorded services this version does not know;
    a downgrade must not silently discard their answers."""
    env_path = tmp_path / ".env"
    env_path.write_text(
        f"{local.OPTIONAL_SERVICES_ENV_KEY}=futureservice:yes\n", encoding="utf-8"
    )

    local._record_optional_service_decision(env_path, "alerts", True)

    line = env_path.read_text(encoding="utf-8")
    assert "futureservice:yes" in line
    assert "alerts:yes" in line
    assert local._read_optional_service_decisions(env_path) == {"alerts": True}


def test_setup_with_alerts_flag_records_and_splices(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stub_env_generators(monkeypatch)

    result = CliRunner().invoke(local.setup, ["--with-alerts"])

    assert result.exit_code == 0, result.output
    env_contents = (Path(tmp_path) / ".env").read_text(encoding="utf-8")
    assert f"{local.OPTIONAL_SERVICES_ENV_KEY}=alerts:yes" in env_contents
    compose = (Path(tmp_path) / "docker-compose.yml").read_text(encoding="utf-8")
    assert "container_name: arcsecond-alerts" in compose
    assert "docs.arcsecond.io" in result.output


def test_setup_non_interactive_run_skips_the_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stub_env_generators(monkeypatch)
    monkeypatch.setattr(local, "_stdin_is_interactive", lambda: False)

    result = CliRunner().invoke(local.setup, [])

    assert result.exit_code == 0, result.output
    env_contents = (Path(tmp_path) / ".env").read_text(encoding="utf-8")
    assert local.OPTIONAL_SERVICES_ENV_KEY not in env_contents
    compose = (Path(tmp_path) / "docker-compose.yml").read_text(encoding="utf-8")
    assert "arcsecond:alerts" not in compose
    assert "Skipping optional-service prompts" in result.output


def test_setup_prompt_decline_is_recorded_and_not_reasked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stub_env_generators(monkeypatch)
    monkeypatch.setattr(local, "_stdin_is_interactive", lambda: True)

    first = CliRunner().invoke(local.setup, [], input="n\n")
    assert first.exit_code == 0, first.output
    env_contents = (Path(tmp_path) / ".env").read_text(encoding="utf-8")
    assert f"{local.OPTIONAL_SERVICES_ENV_KEY}=alerts:no" in env_contents

    # No input provided: a re-prompt would abort the run.
    second = CliRunner().invoke(local.setup, [])
    assert second.exit_code == 0, second.output
    assert "Include the optional" not in second.output
