"""
Read-only diagnostic for an ASCOM Alpaca *telescope* (mount) device.

What a mount driver says about itself decides what a client can do with it,
and drivers in the field say surprising things: a DFM answers 0 for focal
length, aperture and area rather than raising NotImplemented, and declares a
topocentric (JNow) equatorial system where the software feeding it assumed
J2000. This probe writes those answers down verbatim, along with the
``SupportedActions`` list and the passthrough behaviour, so the client side
can be built on evidence rather than on the interface specification.

Axis rates are read only for an axis the driver says it can move. One mount
driver in the field takes its whole ASCOM Remote server down on a GET to
``AxisRates``, and the answer for an immovable axis is meaningless anyway.

The engine lives in :mod:`.probe`; this module owns the property list and
the axis section.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Callable, Iterable

from .probe import (
    ProbeCounts,
    ProbeProgress,
    ProbeResult,
    capture,
)
from .probe import iter_probe_labels as _iter_probe_labels
from .probe import (
    probe_device,
    record,
)

# Read-only descriptors, optics, site, pointing, motion state and capabilities,
# in the order we want them presented. Names are PascalCase to match alpyca.
# ``TargetRightAscension`` / ``TargetDeclination`` are left out on purpose:
# they raise until a target is set, which says nothing about the driver.
_READ_ONLY_PROPERTIES: tuple[str, ...] = (
    "Name",
    "Description",
    "DriverInfo",
    "DriverVersion",
    "InterfaceVersion",
    # Optics and frame: the answers a DFM gives 0 / JNow for.
    "AlignmentMode",
    "EquatorialSystem",
    "ApertureDiameter",
    "ApertureArea",
    "FocalLength",
    "DoesRefraction",
    # Site.
    "SiteLatitude",
    "SiteLongitude",
    "SiteElevation",
    # Clocks and pointing.
    "UTCDate",
    "SiderealTime",
    "RightAscension",
    "Declination",
    "Altitude",
    "Azimuth",
    "SideOfPier",
    # Motion state and rates.
    "Tracking",
    "TrackingRate",
    "TrackingRates",
    "RightAscensionRate",
    "DeclinationRate",
    "GuideRateRightAscension",
    "GuideRateDeclination",
    "Slewing",
    "AtHome",
    "AtPark",
    "IsPulseGuiding",
    "SlewSettleTime",
    # Capabilities.
    "CanFindHome",
    "CanPark",
    "CanUnpark",
    "CanSetPark",
    "CanPulseGuide",
    "CanSetGuideRates",
    "CanSetTracking",
    "CanSetRightAscensionRate",
    "CanSetDeclinationRate",
    "CanSetPierSide",
    "CanSlew",
    "CanSlewAsync",
    "CanSlewAltAz",
    "CanSlewAltAzAsync",
    "CanSync",
    "CanSyncAltAz",
)


class _TelescopeAxis(IntEnum):
    """ASCOM ``TelescopeAxes``. Declared here rather than imported from alpyca
    so the module stays cheap to import; alpyca only reads ``.value`` off what
    it is handed, which a plain int does not have."""

    primary = 0  # RA / Az
    secondary = 1  # Dec / Alt
    tertiary = 2  # rotator / de-rotator


_AXIS_RATES_SKIPPED = "CanMoveAxis is not True, so the driver was not asked for rates."


def _probe_axes(telescope: Any, progress: ProbeProgress, counts: ProbeCounts) -> dict:
    """``CanMoveAxis`` per axis, and ``AxisRates`` only where it answered True."""
    section: dict = {}
    for axis in _TelescopeAxis:
        name = axis.name
        can_move = record(
            capture(lambda a=axis: telescope.CanMoveAxis(a)),
            f"CanMoveAxis({name})",
            progress,
            counts,
        )
        entry: dict = {"axis": int(axis), "CanMoveAxis": can_move}
        if can_move["ok"] and can_move["value"] is True:
            entry["AxisRates"] = record(
                capture(lambda a=axis: telescope.AxisRates(a)),
                f"AxisRates({name})",
                progress,
                counts,
            )
        else:
            entry["axis_rates_skipped_reason"] = _AXIS_RATES_SKIPPED
        section[name] = entry
    return section


def probe_telescope(
    host: str,
    port: int,
    device_number: int = 0,
    *,
    protocol: str = "http",
    allow_active: bool = False,
    collect_host_info: bool | None = None,
    telescope_factory: Callable[[str, int, str], Any] | None = None,
    progress: ProbeProgress | None = None,
) -> ProbeResult:
    """
    Build a JSON-serialisable diagnostic report for an Alpaca telescope at
    ``protocol://host:port`` (device_number). See :func:`.probe.probe_device`
    for the ``collect_host_info`` semantics.

    ``telescope_factory(address, device_number, protocol)`` is only there for
    tests — production callers leave it ``None`` and the real
    ``alpaca.telescope.Telescope`` is used.
    """
    if telescope_factory is None:
        from alpaca.telescope import Telescope  # local import: keep cost off cold paths

        telescope_factory = Telescope

    return probe_device(
        "telescope",
        host,
        port,
        device_number,
        properties=_READ_ONLY_PROPERTIES,
        device_factory=telescope_factory,
        protocol=protocol,
        allow_active=allow_active,
        collect_host_info=collect_host_info,
        extra_probes={"axes": _probe_axes},
        progress=progress,
    )


def iter_probe_labels() -> Iterable[str]:
    """Convenience for tests / docs: enumerate the labels emitted by a run."""
    axis_labels = [f"CanMoveAxis({a.name})" for a in _TelescopeAxis] + [
        f"AxisRates({a.name})" for a in _TelescopeAxis
    ]
    return _iter_probe_labels(_READ_ONLY_PROPERTIES, extra_labels=axis_labels)
