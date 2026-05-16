import gzip
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click

from arcsecond.options import basic_options

from .utils import _read_env_value

DB_CONTAINER = "arcsecond-db"
API_CONTAINER = "arcsecond-api"
WORKER_CONTAINER = "arcsecond-worker"
BEAT_CONTAINER = "arcsecond-beat"
WEB_CONTAINER = "arcsecond-web"

# Services to stop before wiping the DB. db is kept up so we can talk to it.
SERVICES_TO_STOP = [API_CONTAINER, WORKER_CONTAINER, BEAT_CONTAINER, WEB_CONTAINER]

BACKUP_PATTERN = re.compile(r"^backup-(\d{8}-\d{6})\.sql\.gz$")
PRE_RESTORE_PREFIX = "pre-restore-"

STATUS_OK = "compatible"
STATUS_FORWARD = "forward-migrate"
STATUS_INCOMPAT = "incompatible"
STATUS_UNKNOWN = "unknown"


def _cwd_env_path():
    return Path.cwd() / ".env"


def _backups_dir():
    shared = _read_env_value("SHARED_DATA_PATH")
    if not shared:
        return None
    return Path(shared) / "db_backups"


def _print_wrong_dir_hint():
    click.echo(
        "Could not find an Arcsecond.local installation in the current directory.\n"
        "Run `arcsecond backups ...` from the directory that contains your "
        "docker-compose.yml and .env files (the one you used for `arcsecond setup`)."
    )


def _ensure_install_dir():
    """Return the backups dir, or None after printing a clear error."""
    if not _cwd_env_path().exists():
        _print_wrong_dir_hint()
        return None
    backups_dir = _backups_dir()
    if backups_dir is None:
        click.echo(
            "SHARED_DATA_PATH is not set in .env. "
            "Re-run `arcsecond setup` from the Arcsecond.local install directory."
        )
        return None
    if not backups_dir.exists():
        click.echo(
            f"No backups directory found at: {backups_dir.resolve()}\n"
            "Make sure you run this command from the Arcsecond.local working directory "
            "(the one with docker-compose.yml and .env), and that the backend has been "
            "started at least once — the boot-time backup is the first to appear."
        )
        return None
    return backups_dir


def _list_backup_files(backups_dir):
    """Return sorted (newest first) list of (Path, datetime) tuples."""
    items = []
    for entry in backups_dir.iterdir():
        if not entry.is_file():
            continue
        m = BACKUP_PATTERN.match(entry.name)
        if not m:
            continue
        try:
            ts = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        items.append((entry, ts))
    items.sort(key=lambda x: x[1], reverse=True)
    return items


def _human_size(num_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


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


def _extract_backup_migrations(backup_path):
    """Stream the gzipped SQL dump and pull the django_migrations COPY block.

    Returns a set of (app, name) tuples, or None if the table block wasn't found.
    """
    migrations = set()
    in_copy = False
    try:
        with gzip.open(backup_path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not in_copy:
                    if (
                        line.startswith("COPY public.django_migrations")
                        and "FROM stdin" in line
                    ):
                        in_copy = True
                    continue
                if line.startswith("\\."):
                    return migrations
                parts = line.rstrip("\n").split("\t")
                # columns: id, app, name, applied
                if len(parts) >= 3:
                    migrations.add((parts[1], parts[2]))
    except OSError:
        return None
    return migrations if in_copy else None


def _current_code_migrations():
    """Return set of (app, name) migrations known to the current backend image.

    Returns None if the api container isn't running or showmigrations fails.
    """
    if not _container_running(API_CONTAINER):
        return None
    try:
        out = subprocess.run(
            [
                "docker",
                "exec",
                API_CONTAINER,
                "python",
                "manage.py",
                "showmigrations",
                "--plan",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    migrations = set()
    # Lines look like: "[X]  app.0001_initial" or "[ ]  app.0002_thing"
    for line in out.stdout.splitlines():
        m = re.match(r"^\s*\[[ X*]\]\s+([\w_]+)\.(\w+)", line)
        if m:
            migrations.add((m.group(1), m.group(2)))
    return migrations or None


def _compute_compat(backup_migs, code_migs):
    """Return (status, only_in_backup, only_in_code)."""
    if code_migs is None or backup_migs is None:
        return STATUS_UNKNOWN, set(), set()
    only_in_backup = backup_migs - code_migs
    only_in_code = code_migs - backup_migs
    if only_in_backup:
        status = STATUS_INCOMPAT
    elif only_in_code:
        status = STATUS_FORWARD
    else:
        status = STATUS_OK
    return status, only_in_backup, only_in_code


_STATUS_BADGE = {
    STATUS_OK: click.style("✅ compatible", fg="green"),
    STATUS_FORWARD: click.style("⚠️  forward-migrate", fg="yellow"),
    STATUS_INCOMPAT: click.style("❌ incompatible", fg="red"),
    STATUS_UNKNOWN: click.style("?  unknown", fg="white"),
}


def _select_backup(items, ref):
    """Resolve a CLI ref (1-based index or filename) to a Path."""
    if ref is None:
        return None
    if ref.isdigit():
        idx = int(ref)
        if 1 <= idx <= len(items):
            return items[idx - 1][0]
        return None
    for path, _ in items:
        if path.name == ref:
            return path
    return None


def _interactive_pick(items):
    click.echo("")
    idx_str = click.prompt(
        "Enter the index of the backup to restore (or 'q' to cancel)",
        default="q",
        show_default=False,
    )
    if idx_str.lower() in ("q", "quit", "cancel"):
        return None
    if not idx_str.isdigit():
        click.echo("Not a valid index.")
        return None
    n = int(idx_str)
    if not (1 <= n <= len(items)):
        click.echo("Index out of range.")
        return None
    return items[n - 1][0]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@click.group(help="Browse and restore Arcsecond.local DB backups.")
def backups():
    pass


@backups.command(
    name="list", help="List available DB backups with compatibility status."
)
@basic_options
def list_cmd():
    backups_dir = _ensure_install_dir()
    if backups_dir is None:
        sys.exit(1)

    click.echo(f"Reading from: {backups_dir.resolve()}")

    items = _list_backup_files(backups_dir)
    if not items:
        click.echo(f"No backups found in {backups_dir}.")
        click.echo(
            "Backups are created by the backend on each boot and then hourly. "
            "If the backend has started at least once, check the "
            "directory's permissions."
        )
        return

    code_migs = _current_code_migrations()
    if code_migs is None:
        click.echo(
            click.style(
                "Note: backend container is not running — compatibility cannot be checked.",
                fg="yellow",
            )
        )

    click.echo("")
    click.echo(f"{'#':>3}  {'Timestamp (UTC)':<20}  {'Size':>10}  Status")
    click.echo("-" * 70)
    for i, (path, ts) in enumerate(items, start=1):
        backup_migs = _extract_backup_migrations(path) if code_migs else None
        status, _, _ = _compute_compat(backup_migs, code_migs)
        click.echo(
            f"{i:>3}  {ts.strftime('%Y-%m-%d %H:%M:%S'):<20}  "
            f"{_human_size(path.stat().st_size):>10}  {_STATUS_BADGE[status]}"
        )
    click.echo("")
    click.echo(f"{len(items)} backup(s) in {backups_dir}")


@backups.command(name="inspect", help="Show detailed info about a backup.")
@click.argument("ref", required=True)
@basic_options
def inspect_cmd(ref):
    backups_dir = _ensure_install_dir()
    if backups_dir is None:
        sys.exit(1)

    items = _list_backup_files(backups_dir)
    path = _select_backup(items, ref)
    if path is None:
        click.echo(f"No backup matches '{ref}'.")
        sys.exit(1)

    stat = path.stat()
    click.echo("")
    click.echo(f"File:        {path}")
    click.echo(f"Size:        {_human_size(stat.st_size)} ({stat.st_size} bytes)")
    click.echo(
        f"Modified:    {datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()}"
    )

    backup_migs = _extract_backup_migrations(path)
    if backup_migs is None:
        click.echo("Migrations:  could not read django_migrations from dump.")
        return
    click.echo(f"Migrations:  {len(backup_migs)} recorded in dump")

    code_migs = _current_code_migrations()
    if code_migs is None:
        click.echo("Compat:      backend not running — skip migration diff.")
        return

    status, only_in_backup, only_in_code = _compute_compat(backup_migs, code_migs)
    click.echo(f"Compat:      {_STATUS_BADGE[status]}")
    if only_in_code:
        click.echo(
            f"  + {len(only_in_code)} migration(s) will be applied on next backend boot:"
        )
        for app, name in sorted(only_in_code):
            click.echo(f"      {app}.{name}")
    if only_in_backup:
        click.echo(
            f"  - {len(only_in_backup)} migration(s) in backup not in current code:"
        )
        for app, name in sorted(only_in_backup):
            click.echo(f"      {app}.{name}")


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


def _run(cmd, dry_run, **kwargs):
    """Run a command unless dry_run; always log it. Returns CompletedProcess or None."""
    click.echo(click.style(f"$ {' '.join(cmd)}", fg="cyan"))
    if dry_run:
        return None
    return subprocess.run(cmd, **kwargs)


def _take_safety_backup(backups_dir, dry_run):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = backups_dir / f"{PRE_RESTORE_PREFIX}{timestamp}.sql.gz"
    db_user = _read_env_value("POSTGRES_USER") or "arcsecond_docker"
    db_name = _read_env_value("POSTGRES_DB") or "arcsecond_docker"
    db_password = _read_env_value("POSTGRES_PASSWORD") or ""

    click.echo(click.style(f"Creating safety backup: {target.name}", fg="cyan"))
    click.echo(
        click.style(
            f"$ docker exec -e PGPASSWORD=*** {DB_CONTAINER} pg_dump -U {db_user} -d {db_name} "
            f"-F plain  |  gzip > {target}",
            fg="cyan",
        )
    )
    if dry_run:
        return target

    with gzip.open(target, "wb") as out_f:
        proc = subprocess.Popen(
            [
                "docker",
                "exec",
                "-e",
                f"PGPASSWORD={db_password}",
                DB_CONTAINER,
                "pg_dump",
                "-U",
                db_user,
                "-d",
                db_name,
                "-F",
                "plain",
            ],
            stdout=subprocess.PIPE,
        )
        try:
            assert proc.stdout is not None
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                out_f.write(chunk)
            rc = proc.wait()
        finally:
            if proc.poll() is None:
                proc.terminate()
        if rc != 0:
            try:
                target.unlink()
            except OSError:
                pass
            raise RuntimeError(f"pg_dump failed with exit code {rc}")
    return target


def _drop_and_recreate_db(dry_run):
    db_user = _read_env_value("POSTGRES_USER") or "arcsecond_docker"
    db_name = _read_env_value("POSTGRES_DB") or "arcsecond_docker"
    db_password = _read_env_value("POSTGRES_PASSWORD") or ""

    terminate_sql = (
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname='{db_name}' AND pid<>pg_backend_pid();"
    )
    for sql in (
        terminate_sql,
        f'DROP DATABASE IF EXISTS "{db_name}";',
        f'CREATE DATABASE "{db_name}" OWNER "{db_user}";',
    ):
        cmd = [
            "docker",
            "exec",
            "-e",
            f"PGPASSWORD={db_password}",
            DB_CONTAINER,
            "psql",
            "-U",
            db_user,
            "-d",
            "postgres",
            "-c",
            sql,
        ]
        # Mask password in the printed form
        printable = [
            c if not c.startswith("PGPASSWORD=") else "PGPASSWORD=***" for c in cmd
        ]
        click.echo(click.style(f"$ {' '.join(printable)}", fg="cyan"))
        if dry_run:
            continue
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"psql failed: {res.stderr.strip()}")


def _restore_dump(backup_path, dry_run):
    db_user = _read_env_value("POSTGRES_USER") or "arcsecond_docker"
    db_name = _read_env_value("POSTGRES_DB") or "arcsecond_docker"
    db_password = _read_env_value("POSTGRES_PASSWORD") or ""

    click.echo(
        click.style(
            f"$ gunzip -c {backup_path} | docker exec -i -e PGPASSWORD=*** "
            f"{DB_CONTAINER} psql -U {db_user} -d {db_name}",
            fg="cyan",
        )
    )
    if dry_run:
        return

    psql = subprocess.Popen(
        [
            "docker",
            "exec",
            "-i",
            "-e",
            f"PGPASSWORD={db_password}",
            DB_CONTAINER,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            db_user,
            "-d",
            db_name,
        ],
        stdin=subprocess.PIPE,
    )
    try:
        with gzip.open(backup_path, "rb") as f:
            assert psql.stdin is not None
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                psql.stdin.write(chunk)
            psql.stdin.close()
        rc = psql.wait()
    finally:
        if psql.poll() is None:
            psql.terminate()
    if rc != 0:
        raise RuntimeError(f"psql restore failed with exit code {rc}")


@backups.command(
    name="restore",
    help="Restore a DB backup. Stops the backend, wipes the DB, "
    "pipes the dump back in, then restarts the backend.",
)
@click.argument("ref", required=False)
@click.option("--force", is_flag=True, help="Bypass the incompatible-backup block.")
@click.option(
    "--dry-run", is_flag=True, help="Print every command that would run; do nothing."
)
@click.option(
    "--no-safety-backup", is_flag=True, help="Skip the pre-restore safety snapshot."
)
@basic_options
def restore_cmd(ref, force, dry_run, no_safety_backup):
    backups_dir = _ensure_install_dir()
    if backups_dir is None:
        sys.exit(1)

    if not _read_env_value("POSTGRES_PASSWORD"):
        click.echo("POSTGRES_PASSWORD missing from .env — refusing to restore.")
        sys.exit(1)

    items = _list_backup_files(backups_dir)
    if not items:
        click.echo(f"No backups available in {backups_dir}.")
        sys.exit(1)

    if ref is None:
        # Interactive picker — print the list first
        ctx = click.get_current_context()
        ctx.invoke(list_cmd)
        path = _interactive_pick(items)
    else:
        path = _select_backup(items, ref)

    if path is None:
        click.echo("No backup selected.")
        sys.exit(1)

    # Compatibility check
    code_migs = _current_code_migrations()
    backup_migs = _extract_backup_migrations(path) if code_migs is not None else None
    status, only_in_backup, only_in_code = _compute_compat(backup_migs, code_migs)

    click.echo("")
    click.echo(f"Selected backup: {path.name}")
    click.echo(f"Compatibility:   {_STATUS_BADGE[status]}")
    if only_in_code:
        click.echo(
            f"  + {len(only_in_code)} migration(s) will be applied after restore."
        )
    if only_in_backup:
        click.echo(
            f"  - {len(only_in_backup)} migration(s) in backup absent from current code:"
        )
        for app, name in sorted(only_in_backup):
            click.echo(f"      {app}.{name}")

    if status == STATUS_INCOMPAT and not force:
        click.echo(
            click.style(
                "Refusing to restore an incompatible backup. Re-run with --force to override.",
                fg="red",
            )
        )
        sys.exit(1)

    if status == STATUS_UNKNOWN:
        click.echo(
            click.style(
                "Compatibility unknown (backend not running). Restoring without a migration check.",
                fg="yellow",
            )
        )

    # Confirmation: type the filename
    click.echo("")
    click.echo(
        click.style(
            "This will DROP the existing database and replace it with the backup contents.",
            fg="red",
            bold=True,
        )
    )
    typed = click.prompt(
        f"Type the backup filename to confirm ({path.name})", default=""
    )
    if typed != path.name:
        click.echo("Confirmation did not match. Aborted.")
        sys.exit(1)

    started = time.time()

    # Safety backup
    if not no_safety_backup:
        try:
            safety = _take_safety_backup(backups_dir, dry_run)
            click.echo(f"Safety backup: {safety}")
        except Exception as e:
            click.echo(click.style(f"Safety backup failed: {e}", fg="red"))
            sys.exit(1)
    else:
        click.echo(
            click.style("Skipping safety backup (--no-safety-backup).", fg="yellow")
        )

    # Stop services (leave db running)
    for name in SERVICES_TO_STOP:
        if dry_run or _container_running(name):
            _run(["docker", "stop", name], dry_run, capture_output=True, text=True)

    # Wipe & recreate DB
    try:
        _drop_and_recreate_db(dry_run)
    except Exception as e:
        click.echo(click.style(f"DB reset failed: {e}", fg="red"))
        sys.exit(1)

    # Stream dump back in
    try:
        _restore_dump(path, dry_run)
    except Exception as e:
        click.echo(click.style(f"Restore failed: {e}", fg="red"))
        sys.exit(1)

    # Restart api (compose will restart dependents). If compose isn't available,
    # fall back to starting each container by name.
    compose_file = Path.cwd() / "docker-compose.yml"
    if compose_file.exists():
        _run(["docker", "compose", "up", "-d"], dry_run)
    else:
        for name in reversed(SERVICES_TO_STOP):
            _run(["docker", "start", name], dry_run, capture_output=True, text=True)

    elapsed = time.time() - started
    click.echo("")
    click.echo(
        click.style(
            f"Restore completed in {elapsed:.1f}s. The backend will apply any pending "
            f"migrations on startup.",
            fg="green",
        )
    )
