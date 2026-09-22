"""`arcsecond registry login`: the last `docker` command an operator typed.

The images live in a private registry, and pulling them needs a token issued
to the observatory. Until now the installation page asked for
`echo <PAT> | docker login ghcr.io -u arcsecond-io --password-stdin` — a line
with three traps in it: the chevrons that are placeholders, the token landing
in the shell's history, and a `docker` invocation on a page that otherwise has
none. This asks for the token without echoing it, hands it to Docker over a
pipe, and never puts it in a command line — there is deliberately no
`--token` option, because an option ends up in `ps` and in the history.
For a script, `--token-stdin` reads it from standard input instead.
"""

import subprocess
import sys

import click

from arcsecond.errors import ArcsecondError
from arcsecond.options import basic_options

from . import stack

REGISTRY = "ghcr.io"
REGISTRY_USER = "arcsecond-io"


def _run(cmd, token=None):
    try:
        return subprocess.run(
            cmd, input=token, capture_output=True, text=True, check=False, timeout=120
        )
    except FileNotFoundError:
        raise ArcsecondError(stack.DOCKER_NOT_INSTALLED) from None
    except subprocess.TimeoutExpired:
        raise ArcsecondError(stack.DOCKER_NOT_ANSWERING) from None


# registry_group, not registry: the package re-exports it, and `registry` is
# also this module's name.
@click.group(name="registry", help="The private image registry the images come from.")
def registry_group():
    pass


@registry_group.command(
    name="login",
    short_help="Log Docker in to the Arcsecond image registry with your token.",
)
@click.option(
    "--token-stdin",
    is_flag=True,
    help="Read the token from standard input instead of asking for it — for "
    "scripts. There is no --token option on purpose: a token typed as an "
    "option lands in the shell history.",
)
@basic_options
def login(token_stdin):
    """Log Docker in to the Arcsecond image registry, once per machine.

    You are asked for the personal access token Arcsecond gave your
    observatory; nothing is echoed. Docker keeps the login, so `arcsecond
    start` and `arcsecond update` can download the images from then on.
    """
    stack.ensure_docker()
    if token_stdin:
        token = sys.stdin.read().strip()
    else:
        token = click.prompt("Arcsecond registry token", hide_input=True).strip()
    if not token:
        raise ArcsecondError("No token given.")
    if token.startswith("<") and token.endswith(">"):
        raise ArcsecondError(
            "The chevrons are the documentation's way of marking a placeholder: "
            "type the token itself, without them."
        )

    result = _run(
        ["docker", "login", REGISTRY, "-u", REGISTRY_USER, "--password-stdin"],
        token=token + "\n",
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        reason = detail[-1] if detail else "Docker gave no reason"
        raise ArcsecondError(
            f"Docker refused the login: {reason}\n"
            "Check the token (it is the one Arcsecond sent your observatory, not "
            "a GitHub password), or ask team@arcsecond.io for a new one."
        )
    click.echo(
        click.style("Logged in", fg="green")
        + f" to {REGISTRY} as {REGISTRY_USER}. Docker remembers it; "
        "`arcsecond start` can now download the images."
    )


@registry_group.command(
    name="logout", help="Forget the registry login on this machine."
)
@basic_options
def logout():
    stack.ensure_docker()
    result = _run(["docker", "logout", REGISTRY])
    if result.returncode != 0:
        raise ArcsecondError(
            (result.stderr or "").strip() or "Docker could not log out."
        )
    click.echo(f"Logged out of {REGISTRY}.")
