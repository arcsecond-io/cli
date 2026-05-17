import gzip
import os
import re
import subprocess
import sys
import time
import zlib
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
STATUS_BROKEN = "broken"

GZIP_MAGIC = b"\x1f\x8b"


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


def _classify_dump_health(backup_path):
    """Quick check that a dump file looks usable before we try to parse it.

    Returns (True, None) for a readable gzip whose first decompressed bytes
    look like the start of a pg_dump, or (False, reason) for anything that's
    obviously broken: missing gzip magic bytes, truncated, or empty.
    """
    try:
        size = backup_path.stat().st_size
    except OSError as e:
        return False, f"stat failed: {e}"
    if size < len(GZIP_MAGIC):
        return False, f"too small ({size} B)"
    try:
        with open(backup_path, "rb") as f:
            header = f.read(len(GZIP_MAGIC))
        if header != GZIP_MAGIC:
            return False, "not a gzip file (bad magic bytes)"
        with gzip.open(backup_path, "rb") as f:
            chunk = f.read(64)
        if not chunk:
            return False, "gzip is empty"
    except (OSError, EOFError, zlib.error) as e:
        return False, f"unreadable: {e}"
    return True, None


def _extract_backup_migrations(backup_path):
    """Stream the gzipped SQL dump and pull the django_migrations COPY block.

    Returns a set of (app, name) tuples, or None if the table block wasn't found.
    Callers should pre-screen with _classify_dump_health() to avoid spending
    decompression time on obviously-broken files.
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
    """Return (status, only_in_backup, only_in_code, stale_apps).

    `stale_apps` is the subset of backup migrations whose *app label* is
    entirely absent from the running code (e.g. `health_check_db.0001_initial`
    when django-health-check has been removed from INSTALLED_APPS). The
    `django_migrations` row stays in the DB forever, but the migration is
    not actually incompatible with the running code — it's a benign
    leftover. Splitting these out keeps the boot-time backup from being
    permanently flagged red because of a long-uninstalled app.
    """
    if code_migs is None or backup_migs is None:
        return STATUS_UNKNOWN, set(), set(), set()
    only_in_backup_raw = backup_migs - code_migs
    only_in_code = code_migs - backup_migs
    code_apps = {app for app, _ in code_migs}
    stale_apps = {
        (app, name) for app, name in only_in_backup_raw if app not in code_apps
    }
    only_in_backup = only_in_backup_raw - stale_apps
    if only_in_backup:
        status = STATUS_INCOMPAT
    elif only_in_code:
        status = STATUS_FORWARD
    else:
        status = STATUS_OK
    return status, only_in_backup, only_in_code, stale_apps


_STATUS_BADGE = {
    STATUS_OK: click.style("✅ compatible", fg="green"),
    STATUS_FORWARD: click.style("⚠️  older snapshot", fg="yellow"),
    STATUS_INCOMPAT: click.style("❌ incompatible", fg="red"),
    STATUS_UNKNOWN: click.style("?  unknown", fg="white"),
    STATUS_BROKEN: click.style("💥 broken", fg="red"),
}


def _format_status(status, only_in_backup, only_in_code, stale_apps=None):
    """Render the status badge plus an inline migration-delta hint.

    Without a hint, "older snapshot" and "incompatible" look identical to the
    eye even though they describe very different situations. The counts make
    the shape of the diff visible at a glance from the `list` table. Stale
    leftover migrations from uninstalled apps don't appear here — they're
    benign and would only add noise.
    """
    badge = _STATUS_BADGE[status]
    if status == STATUS_FORWARD:
        return f"{badge} (+{len(only_in_code)} migration(s) applied since)"
    if status == STATUS_INCOMPAT:
        parts = []
        if only_in_backup:
            parts.append(f"-{len(only_in_backup)} not in code")
        if only_in_code:
            parts.append(f"+{len(only_in_code)} applied since")
        return f"{badge} ({', '.join(parts)})"
    return badge


def _most_recent_context(status, only_in_backup, only_in_code, stale_apps=None):
    """Plain-English footer for the most recent backup when it isn't ✅.

    The boot-time pre-migration snapshot is the common reason a fresh `list`
    shows the top entry as "older snapshot" (or sometimes "incompatible"
    when migrations have been renamed/removed during development). Spell
    that out so the operator doesn't have to.
    """
    if status == STATUS_FORWARD:
        n = len(only_in_code)
        return (
            f"The most recent backup is a pre-migration snapshot — the {n} "
            f"migration(s) it lacks have already been applied to the running "
            f"DB. This is the normal state right after a successful upgrade. "
            f"Restoring it would roll the database back to its pre-upgrade "
            f"state; the next post-migration backup (boot or hourly) will be "
            f"`compatible`."
        )
    if status == STATUS_INCOMPAT:
        lines = ["The most recent backup is not directly restorable as-is:"]
        if only_in_backup:
            lines.append(
                f"  - it records {len(only_in_backup)} migration(s) no longer "
                f"in the running code (renamed, removed, or squashed during "
                f"development);"
            )
        if only_in_code:
            lines.append(
                f"  - the code has applied {len(only_in_code)} migration(s) "
                f"on top of what the backup recorded."
            )
        lines.append(
            "Restoring will only succeed if you also roll the code back to a "
            "commit that knew the missing migrations. Use `arcsecond backups "
            "inspect 1` to see the exact list."
        )
        return "\n".join(lines)
    return None


def _stale_apps_note(stale_apps):
    """Short note shown alongside list/inspect when uninstalled apps still
    have rows in django_migrations. Mentions the app label(s) so the
    operator can decide whether to clean them up."""
    if not stale_apps:
        return None
    app_labels = sorted({app for app, _ in stale_apps})
    apps_str = ", ".join(app_labels)
    return (
        f"Note: {len(stale_apps)} migration(s) from uninstalled app(s) "
        f"[{apps_str}] are present in the backup's django_migrations table. "
        f"They're harmless leftovers, ignored for compatibility purposes."
    )


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
    broken_count = 0
    most_recent = (
        None  # (status, only_in_backup, only_in_code, stale_apps) for items[0]
    )
    most_recent_stale = set()
    for i, (path, ts) in enumerate(items, start=1):
        healthy, _reason = _classify_dump_health(path)
        only_in_backup, only_in_code, stale_apps = set(), set(), set()
        if not healthy:
            status = STATUS_BROKEN
            broken_count += 1
        elif code_migs is None:
            status = STATUS_UNKNOWN
        else:
            backup_migs = _extract_backup_migrations(path)
            status, only_in_backup, only_in_code, stale_apps = _compute_compat(
                backup_migs, code_migs
            )
        if i == 1:
            most_recent = (status, only_in_backup, only_in_code, stale_apps)
            most_recent_stale = stale_apps
        click.echo(
            f"{i:>3}  {ts.strftime('%Y-%m-%d %H:%M:%S'):<20}  "
            f"{_human_size(path.stat().st_size):>10}  "
            f"{_format_status(status, only_in_backup, only_in_code, stale_apps)}"
        )
    click.echo("")
    click.echo(f"{len(items)} backup(s) in {backups_dir}")
    if broken_count:
        click.echo(
            click.style(
                f"{broken_count} broken dump(s) detected — run "
                "`arcsecond backups inspect <#>` for details, "
                "or delete them to clean up.",
                fg="yellow",
            )
        )
    if most_recent is not None:
        context = _most_recent_context(*most_recent)
        if context:
            click.echo("")
            click.echo(click.style(context, fg="yellow"))
        stale_note = _stale_apps_note(most_recent_stale)
        if stale_note:
            click.echo("")
            click.echo(click.style(stale_note, fg="bright_black"))


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

    healthy, reason = _classify_dump_health(path)
    if not healthy:
        click.echo(f"Health:      {_STATUS_BADGE[STATUS_BROKEN]} — {reason}")
        click.echo(
            "             This file is not a usable backup. Delete it "
            "(`rm <file>`) and rely on a more recent dump."
        )
        return

    backup_migs = _extract_backup_migrations(path)
    if backup_migs is None:
        click.echo("Migrations:  could not read django_migrations from dump.")
        return
    click.echo(f"Migrations:  {len(backup_migs)} recorded in dump")

    code_migs = _current_code_migrations()
    if code_migs is None:
        click.echo("Compat:      backend not running — skip migration diff.")
        return

    status, only_in_backup, only_in_code, stale_apps = _compute_compat(
        backup_migs, code_migs
    )
    click.echo(
        f"Compat:      {_format_status(status, only_in_backup, only_in_code, stale_apps)}"
    )
    if only_in_code:
        click.echo(
            f"  + {len(only_in_code)} migration(s) applied in the running code "
            f"after this backup was taken:"
        )
        for app, name in sorted(only_in_code):
            click.echo(f"      {app}.{name}")
    if only_in_backup:
        click.echo(
            f"  - {len(only_in_backup)} migration(s) recorded in this backup "
            f"but no longer in the running code:"
        )
        for app, name in sorted(only_in_backup):
            click.echo(f"      {app}.{name}")
    if stale_apps:
        click.echo(
            f"  ~ {len(stale_apps)} migration(s) from uninstalled app(s) "
            f"(harmless leftovers, ignored for compatibility):"
        )
        for app, name in sorted(stale_apps):
            click.echo(f"      {app}.{name}")

    context = _most_recent_context(status, only_in_backup, only_in_code, stale_apps)
    if context:
        click.echo("")
        click.echo(click.style(context, fg="yellow"))


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

    # Top-level `SET name = value;` parameters that a newer pg_dump emits but
    # older Postgres servers don't recognize. They're session-level DBA
    # settings, not schema, so dropping them is safe. Add to this list as new
    # forward-incompat parameters appear.


#
# `transaction_timeout` was introduced in PostgreSQL 17, so PG 17 dumps
# break PG 16 restores at the very first SET statement. Filtering it lets
# the rest of the dump apply normally.
_FORWARD_INCOMPAT_SET_PARAMS = ("transaction_timeout",)
_FORWARD_INCOMPAT_SET_RE = re.compile(
    rb"^\s*SET\s+("
    + b"|".join(re.escape(p.encode()) for p in _FORWARD_INCOMPAT_SET_PARAMS)
    + rb")\b",
    re.IGNORECASE,
)


def _iter_filtered_dump_lines(backup_path):
    """Yield dump bytes line-by-line, dropping forward-incompat SET lines.

    Only filters at the head of the file — SET statements deeper in the dump
    are unusual and probably meaningful. "Head" here means everything up to
    the first real DDL/DML statement; SQL/PSQL header noise that does NOT
    close the header window:
      - blank lines
      - SQL comments (`--`)
      - SET statements (we may strip these)
      - psql meta-commands (backslash-prefixed), notably "\\restrict <token>"
        which pg_dump 17.5+ emits; treating that line as "the first real
        statement" would leak the very SET transaction_timeout we exist to
        strip.
    """
    skipped = []
    with gzip.open(backup_path, "rb") as f:
        header_done = False
        for line in f:
            if not header_done:
                stripped = line.lstrip()
                if stripped.startswith(b"SET "):
                    m = _FORWARD_INCOMPAT_SET_RE.match(line)
                    if m:
                        skipped.append(m.group(1).decode())
                        continue
                elif (
                    not stripped
                    or stripped.startswith(b"--")
                    or stripped.startswith(b"\\")
                ):
                    pass
                else:
                    header_done = True
            yield line
    if skipped:
        click.echo(
            click.style(
                f"Skipped {len(skipped)} forward-incompat SET line(s) "
                f"({', '.join(sorted(set(skipped)))}) — these are PostgreSQL "
                f"parameters the destination doesn't recognize. Schema and "
                f"data are unaffected.",
                fg="yellow",
            )
        )


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
        stderr=subprocess.PIPE,
    )
    # Any IO error from writing to / closing psql's stdin almost always means
    # psql already exited (e.g. ON_ERROR_STOP=1 tripped on a SQL error). We
    # swallow the IO error here and let the rc / stderr check below surface
    # the *real* cause — surfacing the Python-side IO error instead just
    # hides what psql actually complained about.
    #
    # We deliberately do NOT use Popen.communicate() to drain stderr: once
    # we've closed stdin ourselves, communicate() tries to flush it again on
    # its way through and raises ValueError("flush of closed file"). Reading
    # stderr directly and then wait()ing sidesteps the whole interaction.
    write_err = None
    stderr_bytes = b""
    try:
        assert psql.stdin is not None
        try:
            for line in _iter_filtered_dump_lines(backup_path):
                psql.stdin.write(line)
        except (BrokenPipeError, OSError, ValueError) as e:
            write_err = e
        finally:
            try:
                psql.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass

        if psql.stderr is not None:
            try:
                stderr_bytes = psql.stderr.read() or b""
            except (OSError, ValueError):
                stderr_bytes = b""
            finally:
                try:
                    psql.stderr.close()
                except (OSError, ValueError):
                    pass

        try:
            rc = psql.wait(timeout=300)
        except subprocess.TimeoutExpired:
            psql.kill()
            rc = psql.wait(timeout=5)
    finally:
        if psql.poll() is None:
            psql.kill()
            psql.wait(timeout=5)

    stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
    if rc != 0:
        if stderr_text:
            click.echo(click.style(stderr_text, fg="red"))
        first_err = stderr_text.splitlines()[0] if stderr_text else None
        detail = f"psql exited {rc}"
        if first_err:
            detail += f": {first_err}"
        raise RuntimeError(detail)
    if write_err is not None:
        # psql exited 0 yet we hit a write error mid-stream. Worth flagging:
        # the dump may not have applied in full.
        if stderr_text:
            click.echo(click.style(stderr_text, fg="yellow"))
        raise RuntimeError(
            f"psql exited 0 but write to its stdin failed: {write_err!r}"
        )


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

    # Refuse outright if the file isn't even a valid gzip dump.
    healthy, reason = _classify_dump_health(path)
    if not healthy:
        click.echo(
            click.style(
                f"Refusing to restore {path.name}: {reason}. "
                "This file is not a usable backup.",
                fg="red",
            )
        )
        sys.exit(1)

    # Compatibility check
    code_migs = _current_code_migrations()
    backup_migs = _extract_backup_migrations(path) if code_migs is not None else None
    status, only_in_backup, only_in_code, stale_apps = _compute_compat(
        backup_migs, code_migs
    )

    click.echo("")
    click.echo(f"Selected backup: {path.name}")
    click.echo(
        f"Compatibility:   {_format_status(status, only_in_backup, only_in_code, stale_apps)}"
    )
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
    if stale_apps:
        click.echo(
            f"  ~ {len(stale_apps)} stale migration(s) from uninstalled app(s) "
            f"(ignored):"
        )
        for app, name in sorted(stale_apps):
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
