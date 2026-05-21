"""
Click command group: ``arcsecond alpaca``.

First citizen: ``arcsecond alpaca probe dome`` — a read-only diagnostic that
captures what surface a given Alpaca dome server exposes (device metadata,
``SupportedActions``, ``CommandString`` / ``CommandBool`` / ``CommandBlind``
passthrough behaviour, and optional local host hints).

Structure leaves room for ``arcsecond alpaca probe telescope`` /
``probe camera`` / ``probe focuser`` and ``arcsecond alpaca discover`` later
under the same group.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import click

from ..errors import ArcsecondError
from .dome_probe import ProbeProgress, probe_dome


@click.group(name="alpaca", help="Diagnostics for local ASCOM Alpaca devices.")
def alpaca_group() -> None:
    pass


@alpaca_group.group(name="probe", help="Inspect an Alpaca device read-only.")
def probe_group() -> None:
    pass


_COMMON_OPTIONS = [
    click.option(
        "--host",
        required=True,
        metavar="HOST",
        help="Alpaca server hostname or IP (without scheme).",
    ),
    click.option(
        "--port",
        type=int,
        required=True,
        metavar="PORT",
        help="Alpaca server TCP port (e.g. 11111).",
    ),
    click.option(
        "--device-number",
        type=int,
        default=0,
        show_default=True,
        help="Alpaca device number on the server.",
    ),
    click.option(
        "--protocol",
        type=click.Choice(["http", "https"], case_sensitive=False),
        default="http",
        show_default=True,
        help="Protocol to reach the Alpaca server with.",
    ),
    click.option(
        "--allow-active",
        is_flag=True,
        default=False,
        help=(
            "Also send CommandBlind and active-class probes. OFF by default "
            "to keep the run safe on real hardware."
        ),
    ),
    click.option(
        "--collect-host-info",
        is_flag=True,
        default=False,
        help=(
            "Additionally collect best-effort local OS hints (open ports, "
            "COM ProgIDs matching TCS/Galil). Read-only."
        ),
    ),
    click.option(
        "--output",
        "output_path",
        type=click.Path(dir_okay=False, writable=True, resolve_path=True),
        default=None,
        help="Where to write the JSON report. Defaults to cwd with a UTC timestamp.",
    ),
]


def _add_options(options):
    def _wrap(fn):
        for opt in reversed(options):
            fn = opt(fn)
        return fn

    return _wrap


def _default_output_path(kind: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return str(Path.cwd() / f"alpaca_{kind}_probe_{stamp}.json")


def _format_progress(label: str, ok: bool, detail: str | None) -> str:
    tag = click.style("[OK ]", fg="green") if ok else click.style("[ERR]", fg="red")
    suffix = f" — {detail}" if detail else ""
    return f"  {tag} {label}{suffix}"


@probe_group.command(
    name="dome",
    help=(
        "Probe a local Alpaca dome device read-only and write a JSON report.\n\n"
        "Captures device metadata, SupportedActions, and the behaviour of the "
        "legacy CommandString / CommandBool / CommandBlind passthroughs. "
        "Useful for figuring out whether a proprietary driver (e.g. TCSGalil) "
        "exposes any vendor-specific extension surface beyond the standard "
        "ASCOM IDome interface."
    ),
)
@_add_options(_COMMON_OPTIONS)
def probe_dome_cmd(
    host: str,
    port: int,
    device_number: int,
    protocol: str,
    allow_active: bool,
    collect_host_info: bool,
    output_path: str | None,
) -> None:
    output_path = output_path or _default_output_path("dome")

    click.echo(
        click.style("Alpaca dome probe", bold=True)
        + f" → {protocol}://{host}:{port} (device {device_number})"
    )
    if allow_active:
        click.echo(
            click.style("  ⚠  ", fg="yellow")
            + "--allow-active is ON: CommandBlind and active-class probes will be sent."
        )

    progress = ProbeProgress(
        on_probe=lambda label, ok, detail: click.echo(
            _format_progress(label, ok, detail)
        )
    )

    try:
        result = probe_dome(
            host=host,
            port=port,
            device_number=device_number,
            protocol=protocol.lower(),
            allow_active=allow_active,
            collect_host_info=collect_host_info,
            progress=progress,
        )
    except RuntimeError as exc:
        raise ArcsecondError(str(exc)) from exc

    try:
        with open(output_path, "w", encoding="utf-8") as fp:
            json.dump(result.report, fp, indent=2, sort_keys=False)
            fp.write("\n")
    except OSError as exc:
        raise ArcsecondError(
            f"Could not write report to {output_path}: {exc}"
        ) from exc

    counts = result.counts
    supported = result.report.get("supported_actions", {})
    supported_n = (
        len(supported.get("value") or []) if supported.get("ok") else 0
    )

    click.echo("")
    click.echo(click.style("Summary", bold=True))
    click.echo(f"  Probes:           {counts.ok}/{counts.total} OK")
    click.echo(f"  SupportedActions: {supported_n} entries")
    click.echo(
        f"  Report written to {click.style(os.fspath(output_path), fg='cyan')}"
    )
