# Rotating the Postgres password on an existing self-hosted install

Until version 3.10, `arcsecond hosting setup` wrote a default Postgres password
(`arcsecond_docker`) into `.env`. New installs now generate a per-install
random password automatically, but **existing installs keep the original weak
password until you rotate it manually** — Postgres only reads
`POSTGRES_PASSWORD` at first container boot to bootstrap the role, so changing
the value in `.env` after the fact does nothing on its own.

This guide rotates the password in three coordinated places: the live database
role, the `.env` file, and the running containers.

## 1. Pick a new password

```bash
NEW_PG_PASSWORD=$(python3 -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip('='))")
echo "$NEW_PG_PASSWORD"
```

Keep this in your shell session — you will paste it into two places.

## 2. Change the password in the live DB

```bash
docker exec -it arcsecond-db psql \
  -U arcsecond_docker \
  -d arcsecond_docker \
  -c "ALTER USER arcsecond_docker WITH PASSWORD '$NEW_PG_PASSWORD';"
```

The role's password is now updated in Postgres. The backend container is
holding open connections that authenticated under the old password — they will
keep working until restart, which is fine; we restart in step 4.

## 3. Update `.env`

Replace the `POSTGRES_PASSWORD=...` line in your `.env` (next to
`docker-compose.yml`) with the new value. Keep the same `POSTGRES_USER` and
`POSTGRES_DB` values — only the password changes.

```bash
sed -i.bak "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$NEW_PG_PASSWORD/" .env
```

(macOS `sed` writes a `.env.bak` backup. Inspect, then delete the backup
once you've confirmed the rewrite worked.)

## 4. Restart the stack

```bash
docker compose restart backend worker beat
```

Backend, worker, and beat re-read `.env` and pick up the new password. The
`db` container itself does **not** need a restart — its data was already
updated in step 2, and a `db` restart would not re-read `POSTGRES_PASSWORD`
anyway (it only does so on first init of an empty volume).

## 5. Verify

```bash
docker compose logs --tail 50 backend | grep -i 'database'
curl -fsS http://localhost:8800/healthcheck/
```

If `healthcheck/` returns 200, you're done.

## File permissions

While you're in `.env`, lock it down so other local users can't read it:

```bash
chmod 600 .env
```

The file holds the Postgres password, the Django `SECRET_KEY`, the field
encryption key, and the JWT signing keys. None of them are useful to an
attacker on their own, but defense in depth is cheap.
