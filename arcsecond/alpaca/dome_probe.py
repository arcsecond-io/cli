"""
Read-only diagnostic for an ASCOM Alpaca *dome* device.

The standard ASCOM Alpaca ``IDome`` interface only exposes a single
``OpenShutter`` / ``CloseShutter`` pair. Multi-shutter domes (e.g. DFM domes
driven by TCSGalil) coordinate their shutters internally; if the driver does
not advertise per-shutter custom actions via ``SupportedActions``, there is
no canonical client-side way to drive the upper and lower shutters
independently.

This module produces a structured JSON report describing exactly what surface
a given Alpaca dome server exposes:

* environment / connectivity
* standard read-only device metadata and dome state
* the raw ``SupportedActions`` list
* legacy ``CommandString`` / ``CommandBool`` / ``CommandBlind`` passthrough
  behaviour against a small set of safe candidate commands
* optional best-effort local host hints (open ports, COM ProgIDs)

It never issues motion-class commands. ``CommandBlind`` and active Galil DMC
verbs are gated behind ``allow_active=True``.
"""

from __future__ import annotations

import os
import platform
import socket
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

# Read-only device descriptors and dome state, in the order we want them
# presented in the report. Names are PascalCase to match the alpyca surface.
_READ_ONLY_PROPERTIES: tuple[str, ...] = (
    "Name",
    "Description",
    "DriverInfo",
    "DriverVersion",
    "InterfaceVersion",
    "ShutterStatus",
    "Altitude",
    "Azimuth",
    "AtHome",
    "AtPark",
    "Slewing",
    "Slaved",
    "CanFindHome",
    "CanPark",
    "CanSetAltitude",
    "CanSetPark",
    "CanSetShutter",
    "CanSlave",
    "CanSyncAzimuth",
)

# Safe Galil DMC read-style verbs: print/report values without commanding
# motion. ``MG`` is "message" (print expression), ``TE`` is "tell error",
# ``TP`` is "tell position".
_READ_ONLY_COMMANDS: tuple[str, ...] = (
    "MG TIME",
    "MG _BGA",
    "TE",
    "TP",
)

# Active commands: kept separate and only sent when allow_active=True.
# ``XQ#STATUS`` jumps to a label called STATUS if it exists; whether that
# label has side effects depends on the driver, hence "active".
_ACTIVE_COMMANDS: tuple[str, ...] = (
    "XQ#STATUS",
)

_RESPONSE_TRUNCATE = 2000


@dataclass
class ProbeProgress:
    """Optional callback bag for streaming progress to the caller (CLI)."""

    on_probe: Callable[[str, bool, str | None], None] | None = None

    def emit(self, label: str, ok: bool, detail: str | None = None) -> None:
        if self.on_probe is not None:
            self.on_probe(label, ok, detail)


@dataclass
class ProbeCounts:
    total: int = 0
    ok: int = 0

    @property
    def failed(self) -> int:
        return self.total - self.ok


@dataclass
class ProbeResult:
    report: dict
    counts: ProbeCounts = field(default_factory=ProbeCounts)


def _truncate(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _RESPONSE_TRUNCATE:
        return value[:_RESPONSE_TRUNCATE] + f"... [truncated, total {len(value)} chars]"
    return value


def _coerce_jsonable(value: Any) -> Any:
    """Make values from alpyca safe to dump as JSON."""
    # IntEnum is a subclass of int, so check it *before* the primitive branch.
    # We want {"name": "shutterClosed", "value": 1} not just 1.
    from enum import Enum
    if isinstance(value, Enum):
        return {"name": value.name, "value": value.value}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_coerce_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _coerce_jsonable(v) for k, v in value.items()}
    return str(value)


def _capture(call: Callable[[], Any]) -> dict:
    """Run ``call()`` and capture either its value or its exception."""
    try:
        raw = call()
    except Exception as exc:  # noqa: BLE001 — errors are data here
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"ok": True, "value": _truncate(_coerce_jsonable(raw))}


def _build_environment(
    host: str,
    port: int,
    device_number: int,
    protocol: str,
    connected_outcome: dict,
) -> dict:
    try:
        from importlib.metadata import PackageNotFoundError, version

        alpaca_version = version("alpyca")
    except PackageNotFoundError:
        alpaca_version = "unknown"
    except Exception:  # noqa: BLE001
        alpaca_version = "unknown"

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "host": host,
        "port": port,
        "device_number": device_number,
        "protocol": protocol,
        "alpyca_version": alpaca_version,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "connected": connected_outcome,
    }


def _probe_device_metadata(
    dome: Any,
    progress: ProbeProgress,
    counts: ProbeCounts,
) -> dict:
    section: dict = {}
    for name in _READ_ONLY_PROPERTIES:
        outcome = _capture(lambda n=name: getattr(dome, n))
        section[name] = outcome
        counts.total += 1
        if outcome["ok"]:
            counts.ok += 1
            progress.emit(name, True, str(outcome["value"]))
        else:
            progress.emit(name, False, outcome["error"])
    return section


def _probe_supported_actions(
    dome: Any,
    progress: ProbeProgress,
    counts: ProbeCounts,
) -> dict:
    outcome = _capture(lambda: dome.SupportedActions)
    counts.total += 1
    if outcome["ok"]:
        counts.ok += 1
        actions = outcome["value"] or []
        progress.emit("SupportedActions", True, f"{len(actions)} entries")
    else:
        progress.emit("SupportedActions", False, outcome["error"])
    return outcome


def _send_command(
    method: Callable[..., Any],
    command: str,
    raw: bool,
) -> dict:
    entry: dict = {"command": command, "raw": raw}
    try:
        response = method(command, raw)
    except Exception as exc:  # noqa: BLE001
        entry.update(ok=False, error=f"{type(exc).__name__}: {exc}")
    else:
        entry.update(ok=True, response=_truncate(_coerce_jsonable(response)))
    return entry


def _probe_command_passthrough(
    dome: Any,
    *,
    allow_active: bool,
    progress: ProbeProgress,
    counts: ProbeCounts,
) -> dict:
    section: dict = {
        "command_string": [],
        "command_bool": [],
        "command_blind": [],
    }

    commands: tuple[str, ...] = _READ_ONLY_COMMANDS
    if allow_active:
        commands = commands + _ACTIVE_COMMANDS

    for cmd in commands:
        entry = _send_command(dome.CommandString, cmd, False)
        section["command_string"].append(entry)
        counts.total += 1
        counts.ok += 1 if entry["ok"] else 0
        progress.emit(
            f"CommandString({cmd!r})",
            entry["ok"],
            entry.get("error") or str(entry.get("response", ""))[:80],
        )

        entry = _send_command(dome.CommandBool, cmd, False)
        section["command_bool"].append(entry)
        counts.total += 1
        counts.ok += 1 if entry["ok"] else 0
        progress.emit(
            f"CommandBool({cmd!r})",
            entry["ok"],
            entry.get("error") or str(entry.get("response", ""))[:80],
        )

    if allow_active:
        # CommandBlind is fire-and-forget — only attempt under --allow-active.
        for cmd in commands:
            entry = _send_command(dome.CommandBlind, cmd, False)
            section["command_blind"].append(entry)
            counts.total += 1
            counts.ok += 1 if entry["ok"] else 0
            progress.emit(
                f"CommandBlind({cmd!r})",
                entry["ok"],
                entry.get("error") or "sent",
            )
    else:
        section["command_blind_skipped_reason"] = (
            "CommandBlind is fire-and-forget; gated behind --allow-active."
        )

    return section


def _safe_subprocess(cmd: list[str], timeout: float = 5.0) -> dict:
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return {"ok": False, "error": f"command not found: {cmd[0]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "returncode": completed.returncode,
        "stdout": _truncate(completed.stdout),
        "stderr": _truncate(completed.stderr),
    }


def _collect_windows_host_hints() -> dict:
    hints: dict = {"os": "windows"}
    hints["netstat"] = _safe_subprocess(["netstat", "-ano"], timeout=8.0)

    progids: list[str] = []
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        hints["com_progids"] = {"ok": False, "error": "winreg unavailable"}
    else:
        try:
            root = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "")
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(root, i)
                except OSError:
                    break
                upper = name.upper()
                if "TCS" in upper or "GALIL" in upper:
                    progids.append(name)
                i += 1
            winreg.CloseKey(root)
            hints["com_progids"] = {"ok": True, "matches": progids}
        except Exception as exc:  # noqa: BLE001
            hints["com_progids"] = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
    return hints


def _collect_posix_host_hints() -> dict:
    hints: dict = {"os": platform.system().lower()}
    # Try ss first (Linux), fall back to lsof (macOS / Linux).
    hints["listening_sockets"] = _safe_subprocess(["ss", "-ltnp"], timeout=5.0)
    if not hints["listening_sockets"].get("ok"):
        hints["listening_sockets"] = _safe_subprocess(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"], timeout=5.0
        )
    return hints


def _collect_host_hints() -> dict:
    if os.name == "nt":
        return _collect_windows_host_hints()
    return _collect_posix_host_hints()


def probe_dome(
    host: str,
    port: int,
    device_number: int = 0,
    *,
    protocol: str = "http",
    allow_active: bool = False,
    collect_host_info: bool = False,
    dome_factory: Callable[[str, int, str], Any] | None = None,
    progress: ProbeProgress | None = None,
) -> ProbeResult:
    """
    Build a JSON-serialisable diagnostic report for an Alpaca dome at
    ``protocol://host:port`` (device_number).

    ``dome_factory(address, device_number, protocol)`` is only there for
    tests — production callers leave it ``None`` and the real
    ``alpaca.dome.Dome`` is used.
    """
    progress = progress or ProbeProgress()
    counts = ProbeCounts()
    address = f"{host}:{port}"

    if dome_factory is None:
        from alpaca.dome import Dome  # local import: keep cost off cold paths

        dome_factory = Dome

    # Build dome client. A failure here is fatal (host unreachable, or the
    # alpyca constructor itself blew up) so we surface it to the caller.
    try:
        dome = dome_factory(address, device_number, protocol)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Could not construct Alpaca Dome client for "
            f"{protocol}://{address} (device {device_number}): "
            f"{type(exc).__name__}: {exc}\n"
            + traceback.format_exc()
        ) from exc

    connected_outcome = _capture(lambda: dome.Connected)
    counts.total += 1
    counts.ok += 1 if connected_outcome["ok"] else 0
    progress.emit(
        "Connected", connected_outcome["ok"],
        connected_outcome.get("error") or str(connected_outcome.get("value")),
    )

    environment = _build_environment(
        host, port, device_number, protocol, connected_outcome
    )

    device_metadata = _probe_device_metadata(dome, progress, counts)
    supported_actions = _probe_supported_actions(dome, progress, counts)
    command_passthrough = _probe_command_passthrough(
        dome,
        allow_active=allow_active,
        progress=progress,
        counts=counts,
    )

    report: dict = {
        "environment": environment,
        "device_metadata": device_metadata,
        "supported_actions": supported_actions,
        "command_passthrough": command_passthrough,
    }

    if collect_host_info:
        report["host_hints"] = _collect_host_hints()

    return ProbeResult(report=report, counts=counts)


def iter_probe_labels() -> Iterable[str]:
    """Convenience for tests / docs: enumerate the labels emitted by a run."""
    yield "Connected"
    yield from _READ_ONLY_PROPERTIES
    yield "SupportedActions"
    for cmd in _READ_ONLY_COMMANDS:
        yield f"CommandString({cmd!r})"
        yield f"CommandBool({cmd!r})"
