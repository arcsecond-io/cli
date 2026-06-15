[![Downloads](http://pepy.tech/badge/arcsecond)](http://pepy.tech/project/arcsecond)
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Farcsecond-io%2Fcli.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2Farcsecond-io%2Fcli?ref=badge_shield)

# Arcsecond CLI

The Command-line interface (CLI) for Arcsecond. It can be used as Python 
module too. The CLI makes it easy to login/register and access Arcsecond resources,
public and private ones.

[Read the docs](https://docs.arcsecond.io/cli)

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


## License
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Farcsecond-io%2Fcli.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2Farcsecond-io%2Fcli?ref=badge_large)