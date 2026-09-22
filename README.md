[![Downloads](http://pepy.tech/badge/arcsecond)](http://pepy.tech/project/arcsecond)
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Farcsecond-io%2Fcli.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2Farcsecond-io%2Fcli?ref=badge_shield)

# Arcsecond CLI

The Command-line interface (CLI) for Arcsecond. It can be used as Python 
module too. The CLI makes it easy to login/register and access Arcsecond resources,
public and private ones.

[Read the docs](https://docs.arcsecond.io/cli)

## Running Arcsecond.local

The CLI owns the whole lifecycle of a self-hosted installation; there is no
`docker` command to type:

```bash
$ arcsecond setup --lan-host 192.168.1.42   # writes .env and docker-compose.yml
$ arcsecond start                           # first run downloads the images
$ arcsecond status
$ arcsecond logs backend -f
$ arcsecond restart backend worker          # after editing .env
$ arcsecond update                          # newer images, refreshed compose file
$ arcsecond stop
```

Every one of these finds the installation in the current folder, or in the
folder `arcsecond setup` last ran in, or where `--dir` points.

## Which server the CLI talks to

The CLI points at one API server at a time — the cloud by default, or a
server you registered, typically your own Arcsecond.local — and every command
follows that pointer:

```bash
$ arcsecond api                     # list them, * marks the current one
$ arcsecond api use local           # `setup` registered `local` for you
$ arcsecond login                   # on that server
```

Credentials are kept per server. For a script or a cron job, `ARCSECOND_API=<name>`
selects a server for that process alone, without moving the pointer.

## Configuration

Credentials and settings live in `~/.config/arcsecond/`, alongside the list of
registered cameras and the live-image proxy's runtime files.

Set `ARCSECOND_CONFIG_DIR` to put them somewhere else:

```bash
$ ARCSECOND_CONFIG_DIR=~/.config/arcsecond-observatory arcsecond login
```

Useful for keeping a personal account and an observatory's apart, and for
containers or CI jobs that should not touch a home directory. Child processes
the CLI starts — such as the background proxy from `arcsecond proxy start` —
inherit it.

# Development

The project uses [uv](https://docs.astral.sh/uv/) for environment and
dependency management. After forking and cloning:

```bash
$ cd ~/arcsecond-cli
$ uv sync --extra webcam --group dev
$ uv run arcsecond --help
$ uv run pytest
```

`uv sync` creates `.venv/` and installs the project with its `webcam` extra
and the `dev` dependency group (pytest, black, flake8, isort). Prefix
commands with `uv run` or activate the venv with `source .venv/bin/activate`.

The test suite writes nothing to your own configuration: an autouse fixture in
`tests/conftest.py` points `ARCSECOND_CONFIG_DIR` at a temporary directory for
the whole run. Several tests save real-looking credentials, so if you add one
that touches `ArcsecondConfig`, leave that fixture in place.


## License
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Farcsecond-io%2Fcli.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2Farcsecond-io%2Fcli?ref=badge_large)