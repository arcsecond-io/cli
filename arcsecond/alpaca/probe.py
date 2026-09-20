"""
The read-only probe engine shared by every ``arcsecond alpaca probe <device>``
command.

A probe never issues motion-class commands. It reads a device's standard
properties, its ``SupportedActions`` list, and how the legacy
``CommandString`` / ``CommandBool`` / ``CommandBlind`` passthroughs behave
against a small set of safe candidate commands, and writes it all out as one
JSON report in which every outcome, including every error, is data.

``CommandBlind`` and active Galil DMC verbs are gated behind
``allow_active=True``. Local host hints (open ports, COM ProgIDs) are attached
automatically when the target is this machine, the only case in which they
describe the Alpaca server's host at all.

Device modules (``dome_probe``, ``telescope_probe``) own only what differs per
device: the property list, the alpyca class, and any extra read-only section.
"""

from __future__ import annotations

import ipaddress
import os
import platform
import socket
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Iterable, Mapping

# Safe Galil DMC read-style verbs: print/report values without commanding
# motion. ``MG`` is "message" (print expression), ``TE`` is "tell error",
# ``TP`` is "tell position". They probe whether a driver forwards
# CommandString at all; a driver without the member (the DFM TCSGalil ones)
# fails every one of them, and that is the finding.
_READ_ONLY_COMMANDS: tuple[str, ...] = (
    "MG TIME",
    "MG _BGA",
    "TE",
    "TP",
)

# Active commands: kept separate and only sent when allow_active=True.
# ``XQ#STATUS`` jumps to a label called STATUS if it exists; whether that
# label has side effects depends on the driver, hence "active".
_ACTIVE_COMMANDS: tuple[str, ...] = ("XQ#STATUS",)

_RESPONSE_TRUNCATE = 2000

# Why a ``host_hints`` section is in a report. The hints describe the machine
# the probe runs on, so by default they are attached only when that is also
# the machine the Alpaca server runs on; ``requested`` marks a caller forcing
# them for a remote target.
HOST_HINTS_REASON_LOCAL = "target-is-local"
HOST_HINTS_REASON_REQUESTED = "requested"

_LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", "::"})


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
    if isinstance(value, Enum):
        return {"name": value.name, "value": value.value}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_coerce_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _coerce_jsonable(v) for k, v in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    # alpyca's ``Rate`` (from AxisRates) carries a range and nothing else.
    if hasattr(value, "Minimum") and hasattr(value, "Maximum"):
        return {
            "minimum": _coerce_jsonable(value.Minimum),
            "maximum": _coerce_jsonable(value.Maximum),
        }
    return str(value)


def capture(call: Callable[[], Any]) -> dict:
    """Run ``call()`` and capture either its value or its exception."""
    try:
        raw = call()
    except Exception as exc:  # noqa: BLE001 — errors are data here
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"ok": True, "value": _truncate(_coerce_jsonable(raw))}


def record(
    outcome: dict, label: str, progress: ProbeProgress, counts: ProbeCounts
) -> dict:
    """Count one captured outcome and report it to the caller; returns it."""
    counts.total += 1
    if outcome["ok"]:
        counts.ok += 1
        progress.emit(label, True, str(outcome["value"]))
    else:
        progress.emit(label, False, outcome["error"])
    return outcome


def _build_environment(
    kind: str,
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
        "device_type": kind,
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
    device: Any,
    properties: Iterable[str],
    progress: ProbeProgress,
    counts: ProbeCounts,
) -> dict:
    section: dict = {}
    for name in properties:
        section[name] = record(
            capture(lambda n=name: getattr(device, n)), name, progress, counts
        )
    return section


def _probe_supported_actions(
    device: Any,
    progress: ProbeProgress,
    counts: ProbeCounts,
) -> dict:
    outcome = capture(lambda: device.SupportedActions)
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
    device: Any,
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
        entry = _send_command(device.CommandString, cmd, False)
        section["command_string"].append(entry)
        counts.total += 1
        counts.ok += 1 if entry["ok"] else 0
        progress.emit(
            f"CommandString({cmd!r})",
            entry["ok"],
            entry.get("error") or str(entry.get("response", ""))[:80],
        )

        entry = _send_command(device.CommandBool, cmd, False)
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
            entry = _send_command(device.CommandBlind, cmd, False)
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


def _address_is_bindable(family: int, address: str) -> bool:
    """Whether ``address`` is assigned to an interface of this machine.

    Binding an ephemeral UDP port is the one portable answer: it succeeds only
    for a local address, needs no privilege, and opens nothing, on Windows,
    macOS and Linux alike.
    """
    try:
        with socket.socket(family, socket.SOCK_DGRAM) as sock:
            sock.bind((address, 0))
    except OSError:
        return False
    return True


def _address_is_local(family: int, address: str) -> bool:
    """Loopback, or assigned to one of this machine's interfaces."""
    try:
        if ipaddress.ip_address(address).is_loopback:
            return True
    except ValueError:
        pass
    return _address_is_bindable(family, address)


def _is_own_hostname(name: str) -> bool:
    """Whether ``name`` is this machine's hostname, qualified or not."""
    local_name = socket.gethostname().lower()
    return name == local_name or name.partition(".")[0] == local_name.partition(".")[0]


def _resolves_to_local_address(name: str) -> bool:
    """Whether any address ``name`` resolves to belongs to this machine."""
    try:
        infos = socket.getaddrinfo(name, None, type=socket.SOCK_DGRAM)
    except OSError:
        return False
    return any(
        _address_is_local(family, str(sockaddr[0]))
        for family, _type, _proto, _canonical, sockaddr in infos
    )


def is_local_target(host: str) -> bool:
    """Whether ``host`` names the machine running the probe.

    The host hints (open ports, COM ProgIDs) describe the machine the probe
    runs on, so they are only worth attaching when that is also the machine
    the Alpaca server runs on. Loopback names, this machine's hostname, and
    any address assigned to one of its interfaces count. A host that does not
    resolve is not local.
    """
    name = host.strip().strip("[]").lower()
    if not name:
        return False
    return (
        name in _LOOPBACK_NAMES
        or _is_own_hostname(name)
        or _resolves_to_local_address(name)
    )


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


def _attach_host_hints(
    report: dict, host: str, target_is_local: bool, collect_host_info: bool | None
) -> None:
    if collect_host_info is None:
        collect_host_info = target_is_local
        reason = HOST_HINTS_REASON_LOCAL
    else:
        reason = HOST_HINTS_REASON_REQUESTED

    if collect_host_info:
        report["host_hints"] = {"collected_because": reason, **_collect_host_hints()}
    elif reason == HOST_HINTS_REASON_REQUESTED:
        report["host_hints_skipped_reason"] = "Disabled by the caller."
    else:
        report["host_hints_skipped_reason"] = (
            f"{host} is not this machine, so the hints would describe the wrong "
            "host; pass --collect-host-info to force them."
        )


ExtraProbe = Callable[[Any, ProbeProgress, ProbeCounts], Any]


def probe_device(
    kind: str,
    host: str,
    port: int,
    device_number: int = 0,
    *,
    properties: tuple[str, ...],
    device_factory: Callable[[str, int, str], Any],
    protocol: str = "http",
    allow_active: bool = False,
    collect_host_info: bool | None = None,
    extra_probes: Mapping[str, ExtraProbe] | None = None,
    progress: ProbeProgress | None = None,
) -> ProbeResult:
    """
    Build a JSON-serialisable diagnostic report for the Alpaca ``kind`` device
    at ``protocol://host:port`` (device_number).

    ``properties`` are read in order into ``device_metadata``. Each
    ``extra_probes`` entry adds a section under its key, right after the
    metadata; it receives the device, the progress sink and the counts.

    ``collect_host_info`` left at ``None`` attaches the local host hints when
    ``host`` is this machine and skips them otherwise, recording which in the
    report. ``True`` forces them for a remote target (they still describe the
    probing machine, not the target); ``False`` skips them for a local one.

    ``device_factory(address, device_number, protocol)`` is the alpyca class
    in production and a stand-in in tests.
    """
    progress = progress or ProbeProgress()
    counts = ProbeCounts()
    address = f"{host}:{port}"

    # Build the client. A failure here is fatal (host unreachable, or the
    # alpyca constructor itself blew up) so we surface it to the caller.
    try:
        device = device_factory(address, device_number, protocol)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Could not construct Alpaca {kind.capitalize()} client for "
            f"{protocol}://{address} (device {device_number}): "
            f"{type(exc).__name__}: {exc}\n" + traceback.format_exc()
        ) from exc

    connected_outcome = record(
        capture(lambda: device.Connected), "Connected", progress, counts
    )

    target_is_local = is_local_target(host)
    environment = _build_environment(
        kind, host, port, device_number, protocol, connected_outcome
    )
    environment["target_is_local"] = target_is_local

    report: dict = {
        "environment": environment,
        "device_metadata": _probe_device_metadata(device, properties, progress, counts),
    }
    for key, run in (extra_probes or {}).items():
        report[key] = run(device, progress, counts)
    report["supported_actions"] = _probe_supported_actions(device, progress, counts)
    report["command_passthrough"] = _probe_command_passthrough(
        device,
        allow_active=allow_active,
        progress=progress,
        counts=counts,
    )

    _attach_host_hints(report, host, target_is_local, collect_host_info)
    return ProbeResult(report=report, counts=counts)


def iter_probe_labels(
    properties: Iterable[str], extra_labels: Iterable[str] = ()
) -> Iterable[str]:
    """Convenience for tests / docs: enumerate the labels emitted by a run."""
    yield "Connected"
    yield from properties
    yield from extra_labels
    yield "SupportedActions"
    for cmd in _READ_ONLY_COMMANDS:
        yield f"CommandString({cmd!r})"
        yield f"CommandBool({cmd!r})"
