"""Database credential management for an Arcsecond.local installation.

This lives in the CLI rather than as a Django management command because the
.env file is on the host, next to docker-compose.yml, and is never mounted
into the containers — compose reads it and injects the values as environment
variables. Nothing running inside arcsecond-api can rewrite it.

Rotating the password means changing two things that must agree:

  * the role's password in the live Postgres cluster, and
  * POSTGRES_PASSWORD in .env, which is what compose feeds to the backend
    (and to the db container, where initdb would use it if the volume were
    ever recreated from scratch).

Postgres only reads POSTGRES_PASSWORD on initdb, so editing .env alone does
nothing to a database that already exists — that asymmetry is exactly what
makes a dedicated command worth having.
"""

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from arcsecond.options import basic_options

from .utils import _container_running, _get_random_postgres_password, _read_env_value

DB_CONTAINER = "arcsecond-db"

# Compose services that hold database credentials and therefore need to be
# recreated to pick up the new .env. `db` is deliberately absent: its password
# now lives in the volume, and POSTGRES_PASSWORD is ignored on a non-empty data
# directory, so recreating it would be downtime for nothing.
SERVICES_TO_RECREATE = ["backend", "worker", "beat"]


def _services_to_recreate():
    """The optional alerts consumer joins the recreate list only when the
    operator's compose file actually carries it — naming an unknown service
    makes `docker compose up` fail outright on installs without the block."""
    services = list(SERVICES_TO_RECREATE)
    compose_path = Path.cwd() / "docker-compose.yml"
    try:
        if "# >>> arcsecond:alerts" in compose_path.read_text(encoding="utf-8"):
            services.append("alerts")
    except OSError:
        pass
    return services


ENV_KEY = "POSTGRES_PASSWORD"

# The .env in the install directory does double duty: compose also reads it to
# expand ${SHARED_DATA_PATH} in docker-compose.yml, so a '$' in a value can be
# swallowed or mangled before it ever reaches a container. Quotes, backslashes,
# '#' and whitespace break either the .env parse or the psql literal. Rather
# than trying to escape our way through all of that, restrict passwords to a
# character set that is unambiguous everywhere.
SAFE_PASSWORD_RE = re.compile(r"^[A-Za-z0-9._~-]+$")
MIN_PASSWORD_LENGTH = 16


def _cwd_env_path():
    return Path.cwd() / ".env"


def _print_wrong_dir_hint():
    click.echo(
        "Could not find an Arcsecond.local installation in the current directory.\n"
        "Run `arcsecond db ...` from the directory that contains your "
        "docker-compose.yml and .env files (the one you used for `arcsecond setup`)."
    )


# Connect to the container's own network address rather than the unix socket or
# loopback. Postgres' stock pg_hba.conf trusts `local`, 127.0.0.1 and ::1
# unconditionally — only non-loopback traffic reaches the scram-sha-256 rule. Over
# a socket, psql therefore succeeds with any password at all, which would make
# both the pre-flight check and the post-rotation verification below meaningless.
# `hostname -i` yields the container IP; keep only the first if there are several.
_PSQL_SHELL = """\
read -r PGPASSWORD
export PGPASSWORD
host=$(hostname -i 2>/dev/null | tr ' ' '\\n' | head -n 1)
[ -n "$host" ] || host=127.0.0.1
exec psql -v ON_ERROR_STOP=1 -q -h "$host" -U "$1" -d "$2" -f -
"""


def _psql(sql, user, password, database="postgres"):
    """Run one SQL statement in the db container, as `user`, authenticating.

    Both the password and the SQL go in over stdin, never in argv: `docker exec
    -e PGPASSWORD=...` would publish the credential to every `ps` on the host,
    which is not a great look for the command whose whole job is to handle
    credentials.
    """
    return subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            DB_CONTAINER,
            "sh",
            "-c",
            _PSQL_SHELL,
            "sh",
            user,
            database,
        ],
        input=f"{password}\n{sql}\n",
        capture_output=True,
        text=True,
        check=False,
    )


def _credentials_work(user, password, database):
    return _psql("SELECT 1;", user, password, database).returncode == 0


def _sql_literal(value):
    """Quote a Postgres string literal.

    With standard_conforming_strings (the default since 9.1) doubling single
    quotes is sufficient — and SAFE_PASSWORD_RE has already ruled out quotes
    and backslashes, so this is belt and braces.
    """
    return "'" + value.replace("'", "''") + "'"


def _validate_password(password):
    """Return an error string, or None when the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"too short: {MIN_PASSWORD_LENGTH} characters minimum."
    if not SAFE_PASSWORD_RE.match(password):
        return (
            "contains characters that are unsafe in a .env file read by docker "
            "compose.\nAllowed: letters, digits, and . _ ~ -\n"
            "In particular '$' is expanded by compose, and quotes, backslashes, "
            "'#' and spaces break the .env parse."
        )
    return None


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


@click.group(name="db", help="Manage the Arcsecond.local database.")
def db():
    pass


@db.command(
    name="set-password",
    help="Rotate the Postgres password, in the database and in .env together.",
)
@click.option(
    "--password",
    default=None,
    help="Password to set. Omit to generate a strong random one (recommended).",
)
@click.option(
    "--show", is_flag=True, help="Print the new password instead of only writing it."
)
@click.option(
    "--no-restart",
    is_flag=True,
    help="Do not recreate the app containers. They keep using the old password "
    "until you recreate them yourself.",
)
@click.option("--dry-run", is_flag=True, help="Show what would happen, change nothing.")
@basic_options
def set_password_cmd(password, show, no_restart, dry_run):
    env_path = _cwd_env_path()
    if not env_path.exists():
        _print_wrong_dir_hint()
        sys.exit(1)

    # Validate the operator's input before anything that needs Docker: a
    # rejected password is a typo to fix, not a reason to go start the stack.
    if password is not None:
        error = _validate_password(password)
        if error:
            click.echo(f"Refusing that password — {error}")
            sys.exit(1)

    db_user = _read_env_value("POSTGRES_USER") or "arcsecond_docker"
    db_name = _read_env_value("POSTGRES_DB") or "arcsecond_docker"
    old_password = _read_env_value(ENV_KEY) or ""

    if not _container_running(DB_CONTAINER):
        click.echo(
            f"The {DB_CONTAINER} container is not running.\n"
            "Start the stack first:  docker compose up -d db"
        )
        sys.exit(1)

    # Rotating from credentials that don't work would just replace one broken
    # state with another, so establish that .env currently matches the cluster.
    click.echo("Checking the current credentials...")
    if not _credentials_work(db_user, old_password, db_name):
        click.echo(
            f"\nCannot authenticate as '{db_user}' with the {ENV_KEY} currently in "
            f"{env_path.name}.\n\n"
            "Fix that mismatch before rotating: .env has to match the password the\n"
            "database volume was initialised with. Installs created before Arcsecond\n"
            "read .env at all were always bootstrapped as\n"
            "'arcsecond_docker'/'arcsecond_docker'."
        )
        sys.exit(1)

    new_password = password if password else _get_random_postgres_password()

    if new_password == old_password:
        click.echo("That is already the current password. Nothing to do.")
        sys.exit(0)

    original_text = env_path.read_text(encoding="utf-8")
    updated_text = _replace_env_value(original_text, ENV_KEY, new_password)
    if updated_text is None:
        click.echo(
            f"No {ENV_KEY} line found in {env_path}. "
            "Re-run `arcsecond setup` from this directory to repair the file."
        )
        sys.exit(1)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = env_path.with_name(f".env.bak-{timestamp}")

    if dry_run:
        click.echo(click.style("\nDry run — nothing was changed.", fg="yellow"))
        click.echo(f"  would back up   {env_path.name} -> {backup_path.name}")
        click.echo(f"  would rewrite   {ENV_KEY} in {env_path.name}")
        click.echo(f"  would run       ALTER ROLE \"{db_user}\" WITH PASSWORD '***'")
        if not no_restart:
            click.echo(
                f"  would recreate  {', '.join(_services_to_recreate())} "
                "(docker compose up -d --force-recreate)"
            )
        sys.exit(0)

    backup_path.write_text(original_text, encoding="utf-8")
    click.echo(f"Backed up {env_path.name} to {backup_path.name}")

    # Write .env before touching the cluster. Either order leaves a window
    # where the two disagree, but a failed ALTER lets us put the file back
    # exactly as it was, whereas a failed write after a successful ALTER would
    # leave the operator holding a password nothing has recorded.
    env_path.write_text(updated_text, encoding="utf-8")

    click.echo(f"Setting the new password for role '{db_user}'...")
    sql = f'ALTER ROLE "{db_user}" WITH PASSWORD {_sql_literal(new_password)};'
    result = _psql(sql, db_user, old_password, db_name)

    if result.returncode != 0:
        env_path.write_text(original_text, encoding="utf-8")
        click.echo(
            click.style(
                f"\nALTER ROLE failed, so {env_path.name} was restored and nothing "
                "changed:\n" + (result.stderr or "").strip(),
                fg="red",
            )
        )
        sys.exit(1)

    if not _credentials_work(db_user, new_password, db_name):
        # The ALTER reported success but the new password does not work. Try to
        # put the cluster back where it was, authenticating with the password we
        # were just told is in effect.
        revert = _psql(
            f'ALTER ROLE "{db_user}" WITH PASSWORD {_sql_literal(old_password)};',
            db_user,
            new_password,
            db_name,
        )
        env_path.write_text(original_text, encoding="utf-8")

        if revert.returncode == 0:
            click.echo(
                click.style(
                    "\nThe new password did not verify; rolled the database and "
                    f"{env_path.name} back to the old one.",
                    fg="red",
                )
            )
        elif _credentials_work(db_user, old_password, db_name):
            # Neither password change took effect, so the cluster is exactly
            # where it started. Nothing is broken — say so plainly rather than
            # sending the operator hunting for a password that was never set.
            click.echo(
                click.style(
                    "\nThe new password did not verify and the database still "
                    f"accepts the old one, so nothing changed. {env_path.name} has "
                    "been restored.",
                    fg="red",
                )
            )
        else:
            click.echo(
                click.style(
                    "\nThe new password did not verify AND the database no longer "
                    "accepts the old one. It may now expect:\n\n"
                    f"    {new_password}\n\n"
                    f"{env_path.name} has been restored to the old value — set it to "
                    "whichever of the two actually works.",
                    fg="red",
                )
            )
        sys.exit(1)

    click.echo(click.style("Password changed and verified.", fg="green"))

    services_to_recreate = _services_to_recreate()
    if no_restart:
        click.echo(
            "\nSkipping the restart, as asked. The running containers still hold the\n"
            "old password and will fail on their next reconnect. Apply it with:\n"
            f"    docker compose up -d --force-recreate {' '.join(services_to_recreate)}"
        )
    else:
        click.echo(f"Recreating {', '.join(services_to_recreate)}...")
        cmd = [
            "docker",
            "compose",
            "up",
            "-d",
            "--force-recreate",
            *services_to_recreate,
        ]
        click.echo(click.style(f"$ {' '.join(cmd)}", fg="cyan"))
        recreate = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if recreate.returncode != 0:
            click.echo(
                click.style(
                    "\nThe password was changed successfully, but recreating the "
                    "containers failed:\n" + (recreate.stderr or "").strip() + "\n\n"
                    "Re-run the command above once Docker is happy.",
                    fg="yellow",
                )
            )
            sys.exit(1)

    if show:
        click.echo(f"\nNew password: {new_password}")
    else:
        click.echo(
            f"\nThe new password is in {env_path.name} (use --show to print it here)."
        )
    click.echo(
        f"Keep {backup_path.name} until you have confirmed the stack is healthy, "
        "then delete it —\nit still contains the old password."
    )
