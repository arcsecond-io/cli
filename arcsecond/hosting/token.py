"""The access token Arcsecond gives an observatory.

From the operator's side there is one fact: Arcsecond sent a token, and it
has to be entered once so the machine can download Arcsecond.local. What it
is underneath — a login to the container registry the images are pulled
from, ghcr.io, as the organisation user — is this module's business, not
theirs, and the words "registry" and "docker" stay out of what they read.

The token is asked for without echo, or read from standard input for a
script, and handed to Docker over a pipe. There is deliberately no
`--token` option: an option lands in `ps` and in the shell's history. Docker
keeps the credential in its own store; this tool keeps nothing.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import click

from arcsecond.errors import ArcsecondError
from arcsecond.options import basic_options

from . import stack

REGISTRY = "ghcr.io"
REGISTRY_USER = "arcsecond-io"

WHAT_IT_IS = "The access token Arcsecond gave your observatory. It lets this machine download Arcsecond.local."


def _run(cmd, token=None):
    try:
        return subprocess.run(
            cmd, input=token, capture_output=True, text=True, check=False, timeout=120
        )
    except FileNotFoundError:
        raise ArcsecondError(stack.DOCKER_NOT_INSTALLED) from None
    except subprocess.TimeoutExpired:
        raise ArcsecondError(stack.DOCKER_NOT_ANSWERING) from None


def docker_config_path() -> Path:
    return (
        Path(os.environ.get("DOCKER_CONFIG") or (Path.home() / ".docker"))
        / "config.json"
    )


def has_token() -> bool:
    """Whether Docker on this machine holds a credential for the images.

    Docker lists the registry under `auths` in its config even when the secret
    itself lives in a credential store (Docker Desktop's, the OS keychain), so
    the key's presence is the answer in the common case. When the config names
    a store and lists nothing, the store is asked.
    """
    try:
        config = json.loads(docker_config_path().read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return False
    auths = config.get("auths") or {}
    if any(REGISTRY in key for key in auths):
        return True
    store = (config.get("credHelpers") or {}).get(REGISTRY) or config.get("credsStore")
    if not store:
        return False
    try:
        probe = subprocess.run(
            [f"docker-credential-{store}", "get"],
            input=f"https://{REGISTRY}\n",
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return probe.returncode == 0 and REGISTRY_USER in (probe.stdout or "")


def store_token(token: str) -> None:
    """Hand the token to Docker; raise with Docker's reason if it is refused."""
    token = (token or "").strip()
    if not token:
        raise ArcsecondError("No token given.")
    if token.startswith("<") and token.endswith(">"):
        raise ArcsecondError(
            "The chevrons are the documentation's way of marking a placeholder: "
            "paste the token itself, without them."
        )
    result = _run(
        ["docker", "login", REGISTRY, "-u", REGISTRY_USER, "--password-stdin"],
        token=token + "\n",
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        reason = detail[-1] if detail else "Docker gave no reason"
        raise ArcsecondError(
            f"The token was refused: {reason}\n"
            "Check it is the token Arcsecond sent your observatory — not an account "
            "password — or ask team@arcsecond.io for a new one."
        )


def prompt_for_token() -> str:
    return click.prompt(
        "Access token from Arcsecond (nothing is shown while you type)", hide_input=True
    ).strip()


# ---------------------------------------------------------------------------
# The commands
# ---------------------------------------------------------------------------


# token_group, not token: the package re-exports it, and `token` is also this
# module's name.
@click.group(name="token", invoke_without_command=True, short_help=WHAT_IT_IS)
@click.pass_context
def token_group(ctx):
    """The access token Arcsecond gave your observatory.

    It lets this machine download Arcsecond.local. `arcsecond setup` asks for
    it; these commands are for entering it again, or removing it.

    \b
      arcsecond token          does this machine have one?
      arcsecond token set      enter it (nothing is shown while you type)
      arcsecond token forget   remove it from this machine
    """
    if ctx.invoked_subcommand is None:
        stack.ensure_docker()
        if has_token():
            click.echo(
                click.style("This machine has the token.", fg="green")
                + " It can download Arcsecond.local."
            )
        else:
            click.echo(
                "This machine has no token yet.\n\nEnter it with:  arcsecond token set"
            )
            raise SystemExit(1)


@token_group.command(
    name="set", short_help="Enter the token (nothing is shown while you type)."
)
@click.option(
    "--stdin",
    "from_stdin",
    is_flag=True,
    help="Read the token from standard input instead of asking — for scripts. "
    "There is no --token option on purpose: a token typed as an option lands in the shell history.",
)
@basic_options
def token_set(from_stdin):
    """Enter the access token Arcsecond gave your observatory, once per machine.

    Nothing is shown while you type or paste it. Docker keeps it, so
    `arcsecond start` and `arcsecond update` can download the images from
    then on.
    """
    stack.ensure_docker()
    token = sys.stdin.read() if from_stdin else prompt_for_token()
    store_token(token)
    click.echo(
        click.style("Token accepted.", fg="green")
        + " This machine can download Arcsecond.local."
    )


@token_group.command(name="forget", short_help="Remove the token from this machine.")
@basic_options
def token_forget():
    stack.ensure_docker()
    result = _run(["docker", "logout", REGISTRY])
    if result.returncode != 0:
        raise ArcsecondError(
            (result.stderr or "").strip() or "The token could not be removed."
        )
    click.echo("Token removed. This machine can no longer download Arcsecond.local.")
