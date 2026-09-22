"""`arcsecond backups` finds the installation the way every other command does."""

from importlib import import_module
from pathlib import Path

from click.testing import CliRunner

from arcsecond.hosting import stack

# The package re-exports the `backups` command group under the module's name, so a
# plain `from arcsecond.hosting import backups` hands back the Group.
backups = import_module("arcsecond.hosting.backups")


def _install(path: Path, shared: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "docker-compose.yml").write_text("services: {}\n")
    (path / ".env").write_text(
        f'SHARED_DATA_PATH="{shared.as_posix()}"\nPOSTGRES_PASSWORD=pw\n'
    )
    (shared / "db_backups").mkdir(parents=True, exist_ok=True)
    return path


def test_list_works_from_another_folder_with_dir(tmp_path, monkeypatch):
    install = _install(tmp_path / "obs", tmp_path / "data")
    monkeypatch.chdir(tmp_path)  # not an installation
    monkeypatch.setattr(backups, "_current_code_migrations", lambda: None)
    monkeypatch.setattr(backups, "_destination_listing", lambda: [])
    result = CliRunner().invoke(backups.backups, ["list", "--dir", str(install)])
    assert result.exit_code == 0, result.output
    assert "Could not find" not in result.output


def test_list_finds_the_remembered_installation(tmp_path, monkeypatch):
    install = _install(tmp_path / "obs", tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    stack.remember_install_dir(install)
    monkeypatch.setattr(backups, "_current_code_migrations", lambda: None)
    monkeypatch.setattr(backups, "_destination_listing", lambda: [])
    result = CliRunner().invoke(backups.backups, ["list"])
    assert result.exit_code == 0, result.output
    assert "Could not find" not in result.output


def test_without_an_installation_it_says_where_it_looked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stack.remember_install_dir(tmp_path / "gone")
    result = CliRunner().invoke(backups.backups, ["list"])
    assert "Could not find an Arcsecond.local installation" in result.output
    assert str(tmp_path) in result.output


def test_env_values_come_from_the_resolved_installation_not_the_cwd(
    tmp_path, monkeypatch
):
    install = _install(tmp_path / "obs", tmp_path / "data")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".env").write_text("POSTGRES_PASSWORD=WRONG\n")
    monkeypatch.chdir(elsewhere)
    assert backups._ensure_install_dir(str(install)) is not None
    assert backups._read_env_value("POSTGRES_PASSWORD") == "pw"


def test_restarting_goes_through_compose_for_this_installation(tmp_path, monkeypatch):
    install = _install(tmp_path / "obs", tmp_path / "data")
    backups._ensure_install_dir(str(install))
    ran = []
    monkeypatch.setattr(backups, "_run", lambda cmd, dry_run, **k: ran.append(cmd))
    backups._start_services(dry_run=False)
    assert ran[0][:2] == ["docker", "compose"]
    assert str(install / "docker-compose.yml") in ran[0]
    assert ran[0][-3:] == ["up", "-d", "--remove-orphans"]


def test_a_missing_backups_folder_no_longer_blames_the_working_directory(
    tmp_path, monkeypatch
):
    install = tmp_path / "obs"
    install.mkdir()
    (install / "docker-compose.yml").write_text("services: {}\n")
    (install / ".env").write_text(
        f'SHARED_DATA_PATH="{(tmp_path / "nodata").as_posix()}"\n'
    )
    monkeypatch.chdir(install)
    result = CliRunner().invoke(backups.backups, ["list"])
    assert "No backups directory found" in result.output
    assert "working directory" not in result.output
