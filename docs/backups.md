# Backups on a self-hosted install

Self-hosted Arcsecond writes a compressed Postgres dump in two situations:

- **On every backend container boot**, before migrations run — so you always
  have a pre-migration snapshot to fall back to if an upgrade goes wrong.
- **Every hour** afterwards, via a Celery periodic task.

A daily cleanup task then prunes dumps older than 14 days. This page covers
where backups live, how to
list / inspect / restore them with the `arcsecond backups` command, and what
else you should copy off-host for full disaster recovery.

## Where backups are stored

Backups are written by the backend to the host directory you picked as
`SHARED_DATA_PATH` during `arcsecond hosting setup`:

```
$SHARED_DATA_PATH/db_backups/
├── backup-20260514-031502.sql.gz       # auto, on boot or hourly
├── backup-20260515-021100.sql.gz
└── pre-restore-20260515-104230.sql.gz  # auto, before any restore
```

- `backup-YYYYMMDD-HHMMSS.sql.gz` — gzipped plain-SQL dump of the entire DB
  (`arcsecond_docker` database, owned by user `arcsecond_docker`). The
  timestamp is in **UTC**.
- `pre-restore-YYYYMMDD-HHMMSS.sql.gz` — safety snapshot taken automatically
  just before any `arcsecond backups restore`.

If you want retention longer than 14 days, ship dumps off-host (see below).

## Listing and inspecting backups

All commands must be run **from the install directory** (the one containing
`docker-compose.yml` and `.env`).

```bash
arcsecond backups list
```

Prints the newest-first table of backups with a compatibility badge against
the currently running backend image. The badge reflects the diff between the
`django_migrations` table recorded in the dump and the migrations shipped by
the image:

- **compatible** — same migration set; restore is safe.
- **forward-migrate** — the running image has newer migrations; restoring is
  safe, the backend will apply them on the next boot.
- **incompatible** — the dump contains migrations the image does not know
  about. Restoring would require downgrading the backend first (or using
  `--force`, which you should not).
- **unknown** — backend container is not running, so no diff is possible.

```bash
arcsecond backups inspect backup-20260515-021100.sql.gz   # or just the index
```

Shows file size, mtime, migration counts, and the exact list of migrations
that differ between the dump and the running image.

## Restoring a backup

```bash
arcsecond backups restore                # interactive picker
arcsecond backups restore 1              # by list index
arcsecond backups restore backup-20260515-021100.sql.gz   # by filename
```

`restore` will, in order:

1. Verify `POSTGRES_PASSWORD` is set in `.env`.
2. Refuse to proceed if the backup is `incompatible` (override with
   `--force`, knowing you may be restoring a dump newer than the code).
3. Take a `pre-restore-…sql.gz` safety snapshot (skip with
   `--no-safety-backup` — not recommended).
4. Stop `arcsecond-api`, `arcsecond-worker`, `arcsecond-beat`,
   `arcsecond-web` (the DB container stays up so the dump can be piped in).
5. Drop and recreate the `arcsecond_docker` database.
6. `gunzip -c <backup> | docker exec -i arcsecond-db psql …`
7. Restart the stopped services.

Use `--dry-run` to print every command without touching anything — useful for
auditing what a restore would do, especially on a production host.

## What else to back up off-host

The auto-dump only covers the Postgres database. For a full disaster
recovery, copy the following to off-host storage (S3, another machine, an
external drive — whatever your operational practice is):

| Path                              | Why                                                                                  |
|-----------------------------------|--------------------------------------------------------------------------------------|
| `$SHARED_DATA_PATH/db_backups/`   | The DB dumps themselves.                                                             |
| `$SHARED_DATA_PATH/`              | All uploaded data files and generated media — Postgres does **not** store these.     |
| `.env`                            | DB password, Django `SECRET_KEY`, `AUTH_JWT_SIGNING_KEY`, `AGENT_JWT_SIGNING_KEY`, `FIELD_ENCRYPTION_KEY`. Without this, a restored DB is unusable: JWT-signed sessions break and field-level encrypted columns become unreadable. Keep it `chmod 600` and treat it like a private key. |
| `docker-compose.yml`              | Only if you have customised it — otherwise `arcsecond hosting setup` rewrites it from the packaged template. |

Putting `.env` and the DB backups in the **same** off-host bucket means an
attacker who breaches that bucket has both the data and the keys. Store them
separately if you can.

## A minimal off-host backup recipe

A simple cron job that ships yesterday's auto-dump plus the secrets:

```bash
#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR=/srv/arcsecond                       # adjust
DEST=s3://your-bucket/arcsecond-backups/$(hostname)
SHARED_DATA_PATH=$(grep '^SHARED_DATA_PATH=' "$INSTALL_DIR/.env" | cut -d= -f2-)

# Latest auto-dump
latest=$(ls -1t "$SHARED_DATA_PATH/db_backups"/backup-*.sql.gz | head -1)
aws s3 cp "$latest" "$DEST/db/"

# Secrets — keep in a separately-permissioned prefix
aws s3 cp "$INSTALL_DIR/.env" "$DEST/secrets/.env"

# Uploaded data (incremental — rclone/restic are usually a better fit here)
aws s3 sync "$SHARED_DATA_PATH/" "$DEST/shared-data/" \
  --exclude "db_backups/*"
```

Restoring on a fresh host: install Arcsecond as usual, replace the generated
`.env` with the backed-up one, drop the dump into
`$SHARED_DATA_PATH/db_backups/`, then run `arcsecond backups restore`.

## Troubleshooting

- **`No backups directory found`** — you are not in the install directory, or
  the backend has never booted on this host. Run from the directory that has
  `docker-compose.yml` and `.env`, and start the stack at least once.
- **`POSTGRES_PASSWORD missing from .env`** — the restore command needs the
  live password to talk to Postgres. If you rotated it manually, make sure
  the `.env` value matches what the role actually has (see
  [rotating the Postgres password](./rotate-postgres-password)).
- **`backend not running — skip migration diff`** during `list` / `inspect` —
  expected when the stack is down. Start the backend if you want the badge.
- **`Refusing to restore an incompatible backup`** — the dump contains
  migrations newer than the running image. Upgrade your image first; do not
  reach for `--force` unless you understand exactly what you are restoring.
