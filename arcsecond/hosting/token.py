"""The access token Arcsecond gives an observatory.

From the operator's side there is one fact: Arcsecond sent a token, and it
has to be entered once so the machine can download Arcsecond.local. What it
is underneath — a login to the container registry the images are pulled
from, ghcr.io, as the organisation user — is this module's business, not
theirs, and the words "registry" and "docker" stay out of what they read —
except when Docker's own password store is what failed, which only they can fix.

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

    When the config names a credential store (Docker Desktop's, `pass`, the OS
    keychain), the store is the truth and is asked: the empty entry Docker
    leaves under `auths` survives a store being emptied or replaced, and a
    machine whose `pass` was never initialised can carry one from an older
    login. Without a store, the secret sits inline under `auths`. Only when
    the store cannot answer — its helper missing, or waiting on a passphrase
    prompt nobody sees — does the entry's presence stand in for it.
    """
    try:
        config = json.loads(docker_config_path().read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return False
    auths = config.get("auths") or {}
    entries = [value for key, value in auths.items() if REGISTRY in key]
    store = (config.get("credHelpers") or {}).get(REGISTRY) or config.get("credsStore")
    if not store:
        return any(isinstance(entry, dict) and entry.get("auth") for entry in entries)
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
        return bool(entries)
    if probe.returncode != 0:
        return False
    try:
        return bool(json.loads(probe.stdout or "{}").get("Secret"))
    except ValueError:
        return False


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
        output = (result.stderr or result.stdout or "").strip()
        if _is_credential_store_failure(output):
            raise ArcsecondError(_credential_store_advice(output))
        detail = output.splitlines()
        reason = detail[-1] if detail else "Docker gave no reason"
        raise ArcsecondError(
            f"The token was refused: {reason}\n"
            "Check it is the token Arcsecond sent your observatory — not an account "
            "password — or ask team@arcsecond.io for a new one."
        )


# Docker only saves the credential once the registry has accepted it, so these
# words mean the token was good and the machine's own keychain failed. Docker
# Desktop on Linux keeps credentials in `pass`, which is empty until someone
# runs `pass init` — it says so in its install notes, and nobody reads them.
_CREDENTIAL_STORE_FAILURES = ("error saving credentials", "error storing credentials")


def _is_credential_store_failure(output: str) -> bool:
    lowered = output.lower()
    return any(words in lowered for words in _CREDENTIAL_STORE_FAILURES)


def _credential_store_advice(output: str) -> str:
    lowered = output.lower()
    head = (
        "The token is good — Arcsecond accepted it — but this machine could not "
        "save it: Docker keeps it in a password store that refused to write.\n"
    )
    if "pass init" in lowered or "pass not initialized" in lowered:
        return head + (
            "Docker Desktop on Linux uses `pass`, and it has not been set up yet. "
            "Set it up once, then run `arcsecond token set` again:\n"
            "    gpg --generate-key          (any name and e-mail; note the key id it prints)\n"
            "    pass init <that key id>\n"
            "Or, if this machine runs Docker Engine without Docker Desktop, remove the "
            f'"credsStore" line from {docker_config_path()} and Docker will keep the '
            "token in that file instead."
        )
    detail = output.splitlines()[-1] if output else ""
    return head + (
        f"It said: {detail}\n"
        'Unlock or repair that store, or remove the "credsStore" line from '
        f"{docker_config_path()} so Docker keeps the token in that file, then run "
        "`arcsecond token set` again."
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
