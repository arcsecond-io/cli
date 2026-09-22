"""
Read-only diagnostic for an ASCOM Alpaca *dome* device.

The standard ASCOM Alpaca ``IDome`` interface only exposes a single
``OpenShutter`` / ``CloseShutter`` pair. Multi-shutter domes (e.g. DFM domes
driven by TCSGalil) coordinate their shutters internally; if the driver does
not advertise per-shutter custom actions via ``SupportedActions``, there is
no canonical client-side way to drive the upper and lower shutters
independently. This probe writes down exactly what surface a dome server
exposes, so that decision can be made on evidence.

The engine, the report layout and the safety rules live in :mod:`.probe`;
this module only says which dome properties to read.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from .probe import ProbeProgress, ProbeResult
from .probe import iter_probe_labels as _iter_probe_labels
from .probe import probe_device

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


def probe_dome(
    host: str,
    port: int,
    device_number: int = 0,
    *,
    protocol: str = "http",
    allow_active: bool = False,
    collect_host_info: bool | None = None,
    dome_factory: Callable[[str, int, str], Any] | None = None,
    progress: ProbeProgress | None = None,
) -> ProbeResult:
    """
    Build a JSON-serialisable diagnostic report for an Alpaca dome at
    ``protocol://host:port`` (device_number). See :func:`.probe.probe_device`
    for the ``collect_host_info`` semantics.

    ``dome_factory(address, device_number, protocol)`` is only there for
    tests — production callers leave it ``None`` and the real
    ``alpaca.dome.Dome`` is used.
    """
    if dome_factory is None:
        from alpaca.dome import Dome  # local import: keep cost off cold paths

        dome_factory = Dome

    return probe_device(
        "dome",
        host,
        port,
        device_number,
        properties=_READ_ONLY_PROPERTIES,
        device_factory=dome_factory,
        protocol=protocol,
        allow_active=allow_active,
        collect_host_info=collect_host_info,
        progress=progress,
    )


def iter_probe_labels() -> Iterable[str]:
    """Convenience for tests / docs: enumerate the labels emitted by a run."""
    return _iter_probe_labels(_READ_ONLY_PROPERTIES)
