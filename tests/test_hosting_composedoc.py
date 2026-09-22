"""The services and environment reference, read from the packaged template."""

from click.testing import CliRunner

from arcsecond import cli
from arcsecond.hosting import composedoc, local


def _services():
    return {s.name: s for s in composedoc.parse_services(local.packaged_compose_text())}


def test_every_service_of_the_template_is_read():
    names = list(
        s.name for s in composedoc.parse_services(local.packaged_compose_text())
    )
    assert names == [
        "db",
        "broker",
        "backend",
        "worker",
        "beat",
        "platesolver",
        "web",
        "alerts",
    ]


def test_facts_are_read_where_the_template_states_them():
    s = _services()
    assert s["backend"].container_name == "arcsecond-api"
    assert s["backend"].image.startswith("ghcr.io/arcsecond-io/arcsecond-api")
    assert s["backend"].ports == ["8800:8800"]
    assert s["backend"].depends_on == ["db", "broker"]
    assert s["backend"].healthcheck is True
    assert s["backend"].stop_grace_period == "60s"
    assert "SHARED_DATA_PATH" in s["backend"].env_vars
    assert s["platesolver"].ports == ["8900:8900"]  # the inline-list form
    assert s["web"].ports == ["5555:5555"]
    assert s["worker"].depends_on == ["backend"]  # the mapping form with a condition
    assert s["db"].ports == [] and s["broker"].ports == []
    assert any("arcsecond_postgres_data" in v for v in s["db"].volumes)
    assert any("/data" in v for v in s["backend"].volumes)


def test_the_comments_are_kept_as_documentation():
    s = _services()
    assert s["db"].description == ["Database (PostgresQL)"]
    assert any("No host port" in n for n in s["db"].notes)
    assert any("host.docker.internal" in n for n in s["backend"].notes)


def test_optional_services_are_recognised_by_their_markers():
    s = _services()
    assert s["alerts"].optional == "alerts"
    assert s["web"].optional is None
    assert "GCN_CONSUMER_CLIENT_ID" in " ".join(s["alerts"].description)


def test_every_key_setup_writes_is_documented():
    for key in local.REQUIRED_ENV_PROVIDERS:
        assert key in composedoc.ENV_KEYS, key
    assert local.OPTIONAL_SERVICES_ENV_KEY in composedoc.ENV_KEYS
    for who, _ in composedoc.ENV_KEYS.values():
        assert who in (composedoc.SETUP, composedoc.OPERATOR, composedoc.BACKEND)


def test_the_pages_render_with_frontmatter_and_the_template_version():
    files = composedoc.generate("9.9.9")
    version = local._compose_version(local.packaged_compose_text())
    for name in ("services.md", "environment.md"):
        page = files[name]
        head = page.split("---")[1]
        assert (
            "source: generated" in head
            and 'cli: "9.9.9"' in head
            and f'template: "{version}"' in head
        )
    services = files["services.md"]
    assert "## `backend`" in services
    assert "| `web` | `arcsecond-web` |" in services
    assert "yes (`alerts`)" in services
    assert "[`SHARED_DATA_PATH`](./environment#shared_data_path)" in services
    environment = files["environment.md"]
    assert "## `POSTGRES_PASSWORD` {#postgres_password}" in environment
    assert "arcsecond db set-password" in environment


def test_rendered_prose_is_safe_for_vitepress():
    for name, page in composedoc.generate("1.0").items():
        body = page.split("---", 2)[2]
        outside_code = "\n".join(
            line
            for line in body.splitlines()
            if "`" not in line and not line.startswith("```")
        )
        assert "<" not in outside_code, name
        assert "{{" not in outside_code, name


def test_the_command_writes_and_checks(tmp_path):
    out = tmp_path / "compose"
    result = CliRunner().invoke(cli.main, ["docs", "compose", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert (out / "services.md").exists() and (out / "environment.md").exists()
    check = CliRunner().invoke(cli.main, ["docs", "compose", "--check", str(out)])
    assert check.exit_code == 0, check.output
    (out / "services.md").write_text("stale\n")
    check = CliRunner().invoke(cli.main, ["docs", "compose", "--check", str(out)])
    assert check.exit_code == 1 and "services.md" in check.output
