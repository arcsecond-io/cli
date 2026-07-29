from pathlib import Path

from click.testing import CliRunner

from arcsecond.hosting import database

ENV_TEMPLATE = """SECRET_KEY=abc
SHARED_DATA_PATH="/tmp/data"
POSTGRES_USER=arcsecond_docker
POSTGRES_PASSWORD={password}
POSTGRES_DB=arcsecond_docker
"""

OLD_PASSWORD = "old-password-0123456789"


def _write_env(tmp_path, password=OLD_PASSWORD):
    env_path = Path(tmp_path) / ".env"
    env_path.write_text(ENV_TEMPLATE.format(password=password), encoding="utf-8")
    return env_path


class FakeCluster:
    """Stands in for the Postgres role, tracking its own password.

    Lets the tests assert the end state of the database and the .env together,
    which is the only property that actually matters here.
    """

    def __init__(self, password=OLD_PASSWORD, alter_fails=False, alter_lies=False):
        self.password = password
        self.alter_fails = alter_fails
        # Reports success but doesn't apply — the case the verify step exists for.
        self.alter_lies = alter_lies
        self.statements = []

    def __call__(self, sql, user, password, database="postgres"):
        class Result:
            def __init__(self, returncode, stderr=""):
                self.returncode = returncode
                self.stderr = stderr
                self.stdout = ""

        if password != self.password:
            return Result(2, 'FATAL: password authentication failed for user "x"')
        self.statements.append(sql)
        if sql.startswith("ALTER ROLE"):
            if self.alter_fails:
                return Result(1, "ERROR: permission denied")
            if not self.alter_lies:
                self.password = sql.split("PASSWORD '", 1)[1].rsplit("';", 1)[0]
        return Result(0)


def _run(tmp_path, monkeypatch, cluster, args=(), recreate_rc=0):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(database, "_psql", cluster)
    monkeypatch.setattr(database, "_container_running", lambda name: True)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = recreate_rc
            stderr = "" if recreate_rc == 0 else "no such service"
            stdout = ""

        return Result()

    monkeypatch.setattr(database.subprocess, "run", fake_run)
    result = CliRunner().invoke(database.db, ["set-password", *args])
    return result, calls


def _capture_psql(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        return Result()

    monkeypatch.setattr(database.subprocess, "run", fake_run)
    database._psql("SELECT 1;", "someuser", "s3cret-password", "somedb")
    return captured


def test_psql_keeps_the_password_out_of_argv(monkeypatch):
    captured = _capture_psql(monkeypatch)

    assert "s3cret-password" not in " ".join(captured["cmd"])
    assert captured["input"].startswith("s3cret-password\n")
    assert "SELECT 1;" in captured["input"]


def test_psql_authenticates_over_a_non_loopback_address(monkeypatch):
    """Stock pg_hba.conf trusts `local`, 127.0.0.1 and ::1 unconditionally.

    A check run over any of those succeeds with any password whatsoever, which
    would silently turn both the pre-flight check and the post-rotation
    verification into no-ops. Only the container's own IP reaches scram-sha-256.
    """
    captured = _capture_psql(monkeypatch)
    shell = captured["cmd"][captured["cmd"].index("-c") + 1]

    assert "hostname -i" in shell
    assert '-h "$host"' in shell


def test_replace_env_value_rewrites_only_the_target_key():
    text = "A=1\nPOSTGRES_PASSWORD=old\n# POSTGRES_PASSWORD=commented\nB=2\n"
    out = database._replace_env_value(text, "POSTGRES_PASSWORD", "new")
    assert out == "A=1\nPOSTGRES_PASSWORD=new\n# POSTGRES_PASSWORD=commented\nB=2\n"


def test_replace_env_value_returns_none_when_key_absent():
    assert database._replace_env_value("A=1\n", "POSTGRES_PASSWORD", "new") is None


def test_rejects_passwords_that_break_compose_env_parsing():
    # '$' is expanded by compose when it reads .env for ${...} substitution.
    assert database._validate_password("dollar$sign-is-not-ok") is not None
    assert database._validate_password('quote"is-not-ok-either') is not None
    assert database._validate_password("short") is not None
    assert database._validate_password("perfectly-fine_password.123~") is None


def test_generated_password_passes_our_own_validation():
    for _ in range(20):
        assert (
            database._validate_password(database._get_random_postgres_password())
            is None
        )


def test_rotation_updates_both_the_database_and_the_env_file(tmp_path, monkeypatch):
    env_path = _write_env(tmp_path)
    cluster = FakeCluster()

    result, calls = _run(tmp_path, monkeypatch, cluster)

    assert result.exit_code == 0, result.output
    new_password = database._read_env_value("POSTGRES_PASSWORD", env_path)
    assert new_password != OLD_PASSWORD
    # The single property that was broken before: the two agree.
    assert cluster.password == new_password
    # Untouched keys survive the rewrite.
    assert database._read_env_value("SECRET_KEY", env_path) == "abc"
    assert database._read_env_value("SHARED_DATA_PATH", env_path) == "/tmp/data"
    # App containers are recreated so they pick up the new env; db is not.
    assert calls == [
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--force-recreate",
            "backend",
            "worker",
            "beat",
        ]
    ]


def test_password_is_not_printed_unless_asked(tmp_path, monkeypatch):
    _write_env(tmp_path)
    cluster = FakeCluster()

    result, _ = _run(tmp_path, monkeypatch, cluster)

    assert cluster.password not in result.output
    assert "--show" in result.output


def test_show_prints_the_new_password(tmp_path, monkeypatch):
    _write_env(tmp_path)
    cluster = FakeCluster()

    result, _ = _run(tmp_path, monkeypatch, cluster, args=["--show"])

    assert cluster.password in result.output


def test_explicit_password_is_used(tmp_path, monkeypatch):
    env_path = _write_env(tmp_path)
    cluster = FakeCluster()

    result, _ = _run(
        tmp_path, monkeypatch, cluster, args=["--password", "chosen-password-123456"]
    )

    assert result.exit_code == 0, result.output
    assert cluster.password == "chosen-password-123456"
    assert (
        database._read_env_value("POSTGRES_PASSWORD", env_path)
        == "chosen-password-123456"
    )


def test_failed_alter_restores_the_env_file(tmp_path, monkeypatch):
    env_path = _write_env(tmp_path)
    before = env_path.read_text(encoding="utf-8")
    cluster = FakeCluster(alter_fails=True)

    result, calls = _run(tmp_path, monkeypatch, cluster)

    assert result.exit_code == 1
    assert env_path.read_text(encoding="utf-8") == before
    assert cluster.password == OLD_PASSWORD
    assert calls == [], "must not recreate containers after a failed rotation"


def test_unverifiable_new_password_leaves_a_consistent_install(tmp_path, monkeypatch):
    """An ALTER that reports success but doesn't apply must not panic anyone.

    The cluster still accepts the old password and .env is restored, so the
    install is exactly as it started — the operator should be told that, not
    handed a password to go hunting for.
    """
    env_path = _write_env(tmp_path)
    before = env_path.read_text(encoding="utf-8")
    cluster = FakeCluster(alter_lies=True)

    result, calls = _run(tmp_path, monkeypatch, cluster)

    assert result.exit_code == 1
    assert env_path.read_text(encoding="utf-8") == before
    assert cluster.password == OLD_PASSWORD
    assert calls == []
    assert "nothing changed" in result.output
    # The password that was never set must not be presented as a thing to try.
    assert "may now expect" not in result.output


def test_refuses_when_current_credentials_do_not_work(tmp_path, monkeypatch):
    env_path = _write_env(tmp_path, password="not-the-live-password")
    before = env_path.read_text(encoding="utf-8")
    cluster = FakeCluster(password=OLD_PASSWORD)

    result, calls = _run(tmp_path, monkeypatch, cluster)

    assert result.exit_code == 1
    assert env_path.read_text(encoding="utf-8") == before
    assert "Cannot authenticate" in result.output
    assert calls == []


def test_bad_password_is_refused_without_needing_docker(tmp_path, monkeypatch):
    """A typo should not require the operator to go start the stack first."""
    env_path = _write_env(tmp_path)
    before = env_path.read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def explode(*args, **kwargs):  # pragma: no cover - must never be reached
        raise AssertionError("Docker must not be touched for an invalid password")

    monkeypatch.setattr(database, "_container_running", explode)
    monkeypatch.setattr(database, "_psql", explode)

    result = CliRunner().invoke(
        database.db, ["set-password", "--password", "has$dollar-and-more"]
    )

    assert result.exit_code == 1
    assert "Refusing that password" in result.output
    assert env_path.read_text(encoding="utf-8") == before


def test_refuses_outside_an_install_directory(tmp_path, monkeypatch):
    result, _ = _run(tmp_path, monkeypatch, FakeCluster())

    assert result.exit_code == 1
    assert "Could not find an Arcsecond.local installation" in result.output


def test_dry_run_changes_nothing(tmp_path, monkeypatch):
    env_path = _write_env(tmp_path)
    before = env_path.read_text(encoding="utf-8")
    cluster = FakeCluster()

    result, calls = _run(tmp_path, monkeypatch, cluster, args=["--dry-run"])

    assert result.exit_code == 0
    assert env_path.read_text(encoding="utf-8") == before
    assert cluster.password == OLD_PASSWORD
    assert calls == []
    assert not list(Path(tmp_path).glob(".env.bak-*"))


def test_backup_of_the_env_file_keeps_the_old_password(tmp_path, monkeypatch):
    _write_env(tmp_path)

    result, _ = _run(tmp_path, monkeypatch, FakeCluster())

    assert result.exit_code == 0, result.output
    backups = list(Path(tmp_path).glob(".env.bak-*"))
    assert len(backups) == 1
    assert database._read_env_value("POSTGRES_PASSWORD", backups[0]) == OLD_PASSWORD


def test_no_restart_leaves_containers_alone_and_says_so(tmp_path, monkeypatch):
    _write_env(tmp_path)
    cluster = FakeCluster()

    result, calls = _run(tmp_path, monkeypatch, cluster, args=["--no-restart"])

    assert result.exit_code == 0, result.output
    assert calls == []
    assert "--force-recreate" in result.output


def test_failed_recreate_reports_but_keeps_the_new_password(tmp_path, monkeypatch):
    env_path = _write_env(tmp_path)
    cluster = FakeCluster()

    result, calls = _run(tmp_path, monkeypatch, cluster, recreate_rc=1)

    assert result.exit_code == 1
    assert len(calls) == 1
    # The rotation itself succeeded, so the file must keep the new value.
    assert database._read_env_value("POSTGRES_PASSWORD", env_path) == cluster.password
    assert "password was changed successfully" in result.output
