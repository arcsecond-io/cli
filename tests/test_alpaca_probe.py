"""
Tests for the ``arcsecond alpaca probe dome`` and ``probe telescope`` CLI
commands.

The real ASCOM Alpaca server is replaced with stubs (``FakeDome``,
``FakeTelescope``) so the suite runs offline. We exercise the CLI through
``click.testing.CliRunner`` to cover both the probe logic and the Click
wiring.
"""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from enum import IntEnum

import pytest
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.alpaca import dome_probe, probe, telescope_probe
from arcsecond.alpaca.dome_probe import probe_dome
from arcsecond.alpaca.probe import is_local_target
from arcsecond.alpaca.telescope_probe import probe_telescope

# Kept so one test can run the real collector after the autouse stub below.
_REAL_COLLECT_HOST_HINTS = probe._collect_host_hints

# TEST-NET-3 (RFC 5737): a documentation range never assigned to a real
# interface, so it is a deterministic "remote" target with no DNS involved.
REMOTE_HOST = "203.0.113.7"


class _NotImplementedException(Exception):
    """Stand-in for alpaca.exceptions.NotImplementedException."""


class _ShutterStatus(IntEnum):
    shutterOpen = 0
    shutterClosed = 1
    shutterOpening = 2
    shutterClosing = 3
    shutterError = 4


class FakeDome:
    """
    Minimal stand-in for ``alpaca.dome.Dome``.

    Mixes successful reads, ``_NotImplementedException``s, and an IntEnum
    so we can verify both the happy path and the error capture path.
    """

    Name = "FakeDome"
    Description = "A pretend dome for tests"
    DriverInfo = ["FakeDome 0.1"]
    DriverVersion = "0.1"
    InterfaceVersion = 3

    def __init__(self, address: str, device_number: int, protocol: str = "http"):
        self.address = address
        self.device_number = device_number
        self.protocol = protocol
        self.command_blind_calls: list[tuple[str, bool]] = []
        self.command_string_calls: list[tuple[str, bool]] = []
        self.command_bool_calls: list[tuple[str, bool]] = []
        # Mark whether *anything* motion-class was sent. Always False in
        # the default (read-only) suite — that's part of what we assert.
        self.motion_invoked = False

    # --- standard read-only props ----------------------------------------

    @property
    def Connected(self) -> bool:
        return True

    @property
    def ShutterStatus(self) -> _ShutterStatus:
        return _ShutterStatus.shutterClosed

    @property
    def Altitude(self) -> float:
        return 12.5

    @property
    def Azimuth(self) -> float:
        return 180.0

    @property
    def AtHome(self) -> bool:
        return False

    @property
    def AtPark(self) -> bool:
        return True

    @property
    def Slewing(self) -> bool:
        return False

    @property
    def Slaved(self) -> bool:
        return False

    @property
    def CanFindHome(self) -> bool:
        return True

    @property
    def CanPark(self) -> bool:
        return True

    @property
    def CanSetAltitude(self) -> bool:
        return False

    @property
    def CanSetPark(self) -> bool:
        return False

    @property
    def CanSetShutter(self) -> bool:
        return True

    @property
    def CanSlave(self) -> bool:
        # Intentionally raises to verify error capture.
        raise _NotImplementedException("CanSlave is not implemented in this driver")

    @property
    def CanSyncAzimuth(self) -> bool:
        return False

    @property
    def SupportedActions(self) -> list[str]:
        return []  # TCSGalil-like: nothing useful

    # --- passthroughs ----------------------------------------------------

    def CommandString(self, command: str, raw: bool = False) -> str:
        self.command_string_calls.append((command, raw))
        if command.startswith("XQ"):
            # Pretend the driver refuses anything that smells active in
            # CommandString — useful to assert default invocation stays read-only.
            self.motion_invoked = True
        return f"FakeDome ack: {command}"

    def CommandBool(self, command: str, raw: bool = False) -> bool:
        self.command_bool_calls.append((command, raw))
        return False

    def CommandBlind(self, command: str, raw: bool = False) -> None:
        self.command_blind_calls.append((command, raw))
        self.motion_invoked = True


@pytest.fixture
def fake_dome_factory():
    """
    Returns a (factory, registry) pair so a single test can both pass the
    factory into probe_dome and inspect the FakeDome it produced.
    """
    registry: list[FakeDome] = []

    def factory(address: str, device_number: int, protocol: str) -> FakeDome:
        dome = FakeDome(address, device_number, protocol)
        registry.append(dome)
        return dome

    return factory, registry


@pytest.fixture(autouse=True)
def _stub_alpaca_in_cli(monkeypatch):
    """
    Replace alpaca.dome.Dome at import time so the CLI command uses FakeDome
    even when it goes through the production factory path.
    """
    # Build a synthetic ``alpaca`` package with the minimal surface
    # dome_probe.probe_dome() touches via its lazy imports.
    import sys
    import types

    alpaca_pkg = types.ModuleType("alpaca")
    alpaca_pkg.__version__ = "test-stub"
    dome_mod = types.ModuleType("alpaca.dome")
    dome_mod.Dome = FakeDome
    telescope_mod = types.ModuleType("alpaca.telescope")
    telescope_mod.Telescope = FakeTelescope
    sys.modules["alpaca"] = alpaca_pkg
    sys.modules["alpaca.dome"] = dome_mod
    sys.modules["alpaca.telescope"] = telescope_mod
    yield
    sys.modules.pop("alpaca", None)
    sys.modules.pop("alpaca.dome", None)
    sys.modules.pop("alpaca.telescope", None)


@pytest.fixture(autouse=True)
def _stub_host_hints(monkeypatch):
    """
    The real collector shells out to netstat/lsof and, on Windows, walks the
    registry. Stub it so the suite stays fast and deterministic; one test
    restores the real one on purpose.
    """
    monkeypatch.setattr(probe, "_collect_host_hints", lambda: {"os": "stub"})


def _make_runner() -> CliRunner:
    return CliRunner()


def test_probe_dome_function_default_is_readonly(fake_dome_factory):
    factory, registry = fake_dome_factory

    result = probe_dome(
        host="127.0.0.1",
        port=11111,
        device_number=0,
        protocol="http",
        dome_factory=factory,
    )

    assert len(registry) == 1
    dome = registry[0]

    # Top-level shape.
    for key in (
        "environment",
        "device_metadata",
        "supported_actions",
        "command_passthrough",
    ):
        assert key in result.report

    # 127.0.0.1 is this machine, so the host hints come for free and say why.
    assert result.report["host_hints"]["collected_because"] == "target-is-local"
    assert "host_hints_skipped_reason" not in result.report

    # Environment captures connectivity.
    env = result.report["environment"]
    assert env["device_type"] == "dome"
    assert env["host"] == "127.0.0.1"
    assert env["port"] == 11111
    assert env["device_number"] == 0
    assert env["target_is_local"] is True
    assert env["connected"]["ok"] is True
    assert env["connected"]["value"] is True

    # Errors are data, not crashes.
    metadata = result.report["device_metadata"]
    assert metadata["Name"] == {"ok": True, "value": "FakeDome"}
    assert metadata["CanSlave"]["ok"] is False
    assert "_NotImplementedException" in metadata["CanSlave"]["error"]

    # IntEnums get expanded to {name, value} for clarity.
    assert metadata["ShutterStatus"]["ok"] is True
    assert metadata["ShutterStatus"]["value"] == {"name": "shutterClosed", "value": 1}

    # SupportedActions is reported even when empty.
    sa = result.report["supported_actions"]
    assert sa["ok"] is True
    assert sa["value"] == []

    # Default run is strictly read-only.
    assert dome.command_blind_calls == []
    assert dome.motion_invoked is False
    assert {cmd for cmd, _ in dome.command_string_calls} == {
        "MG TIME",
        "MG _BGA",
        "TE",
        "TP",
    }
    assert "command_blind_skipped_reason" in result.report["command_passthrough"]

    # Counts are sane.
    assert result.counts.total > 0
    assert result.counts.ok < result.counts.total  # CanSlave intentionally fails


def test_probe_dome_function_allow_active_sends_blind(fake_dome_factory):
    factory, registry = fake_dome_factory

    probe_dome(
        host="127.0.0.1",
        port=11111,
        protocol="http",
        allow_active=True,
        dome_factory=factory,
    )

    dome = registry[0]
    assert (
        dome.command_blind_calls
    ), "CommandBlind should have been invoked under --allow-active"
    blind_commands = {cmd for cmd, _ in dome.command_blind_calls}
    assert "XQ#STATUS" in blind_commands


def test_probe_dome_function_forced_host_info_runs_real_collector(
    fake_dome_factory, monkeypatch
):
    factory, _ = fake_dome_factory
    monkeypatch.setattr(probe, "_collect_host_hints", _REAL_COLLECT_HOST_HINTS)

    result = probe_dome(
        host="127.0.0.1",
        port=11111,
        protocol="http",
        collect_host_info=True,
        dome_factory=factory,
    )
    hints = result.report["host_hints"]
    assert hints["collected_because"] == "requested"
    assert "os" in hints


def test_probe_dome_function_remote_target_skips_host_hints(fake_dome_factory):
    factory, _ = fake_dome_factory

    result = probe_dome(
        host=REMOTE_HOST,
        port=11111,
        protocol="http",
        dome_factory=factory,
    )
    assert result.report["environment"]["target_is_local"] is False
    assert "host_hints" not in result.report
    reason = result.report["host_hints_skipped_reason"]
    assert REMOTE_HOST in reason
    assert "--collect-host-info" in reason


def test_probe_dome_function_remote_target_can_force_host_hints(fake_dome_factory):
    factory, _ = fake_dome_factory

    result = probe_dome(
        host=REMOTE_HOST,
        port=11111,
        protocol="http",
        collect_host_info=True,
        dome_factory=factory,
    )
    assert result.report["host_hints"]["collected_because"] == "requested"
    assert "host_hints_skipped_reason" not in result.report


def test_probe_dome_function_local_target_can_opt_out(fake_dome_factory):
    factory, _ = fake_dome_factory

    result = probe_dome(
        host="127.0.0.1",
        port=11111,
        protocol="http",
        collect_host_info=False,
        dome_factory=factory,
    )
    assert "host_hints" not in result.report
    assert result.report["host_hints_skipped_reason"] == "Disabled by the caller."


@pytest.mark.parametrize(
    "host", ["localhost", "LOCALHOST", "127.0.0.1", "::1", "[::1]", " 127.0.0.1 "]
)
def test_is_local_target_loopback(host):
    assert is_local_target(host) is True


def test_is_local_target_own_hostname():
    assert is_local_target(socket.gethostname()) is True
    assert is_local_target(socket.gethostname().upper()) is True


def test_is_local_target_documentation_address_is_remote():
    assert is_local_target(REMOTE_HOST) is False


def test_is_local_target_unresolvable_or_empty_is_remote(monkeypatch):
    def _no_dns(*args, **kwargs):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", _no_dns)
    assert is_local_target("dome.example.invalid") is False
    assert is_local_target("") is False


def test_cli_writes_json_report(tmp_path):
    runner = _make_runner()
    out = tmp_path / "probe.json"
    result = runner.invoke(
        cli.main,
        [
            "alpaca",
            "probe",
            "dome",
            "--host",
            "127.0.0.1",
            "--port",
            "11111",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert set(data.keys()) >= {
        "environment",
        "device_metadata",
        "supported_actions",
        "command_passthrough",
    }
    # Default invocation against this machine: host_hints attached and
    # attributed, no CommandBlind block populated.
    assert data["host_hints"]["collected_because"] == "target-is-local"
    assert "HOST is this machine" in result.output
    assert data["command_passthrough"]["command_blind"] == []
    assert data["command_passthrough"]["command_blind_skipped_reason"].startswith(
        "CommandBlind is fire-and-forget"
    )


def test_cli_no_host_info_opts_out(tmp_path):
    runner = _make_runner()
    out = tmp_path / "probe.json"
    result = runner.invoke(
        cli.main,
        [
            "alpaca",
            "probe",
            "dome",
            "--host",
            "127.0.0.1",
            "--port",
            "11111",
            "--no-host-info",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert "host_hints" not in data
    assert data["host_hints_skipped_reason"] == "Disabled by the caller."
    assert "Host hints:       skipped" in result.output


def test_cli_remote_host_skips_hints_unless_forced(tmp_path):
    runner = _make_runner()
    out = tmp_path / "probe.json"
    base = ["alpaca", "probe", "dome", "--host", REMOTE_HOST, "--port", "11111"]

    result = runner.invoke(cli.main, base + ["--output", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert "host_hints" not in data
    assert "--collect-host-info" in data["host_hints_skipped_reason"]
    assert "Host hints:       skipped" in result.output

    result = runner.invoke(
        cli.main, base + ["--collect-host-info", "--output", str(out)]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["host_hints"]["collected_because"] == "requested"
    assert "collected (--collect-host-info)" in result.output


def test_cli_default_output_path_in_cwd(tmp_path, monkeypatch):
    runner = _make_runner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli.main,
        [
            "alpaca",
            "probe",
            "dome",
            "--host",
            "127.0.0.1",
            "--port",
            "11111",
        ],
    )
    assert result.exit_code == 0, result.output
    written = list(tmp_path.glob("alpaca_dome_probe_*.json"))
    assert len(written) == 1


def test_cli_progress_lines_emitted(tmp_path):
    runner = _make_runner()
    result = runner.invoke(
        cli.main,
        [
            "alpaca",
            "probe",
            "dome",
            "--host",
            "127.0.0.1",
            "--port",
            "11111",
            "--output",
            str(tmp_path / "probe.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    # Stripped of ANSI styling, we expect at least one OK and one ERR line
    # because FakeDome.CanSlave raises.
    assert "Name" in result.output
    assert "CanSlave" in result.output
    assert "Summary" in result.output


def test_cli_fatal_connection_error_becomes_arcsecond_error(monkeypatch, tmp_path):
    """
    Construction failures (e.g. unreachable host) must surface as
    ``ArcsecondError`` — clean message, non-zero exit, no stack trace.
    """

    class _Boom(FakeDome):
        def __init__(self, *args, **kwargs):
            raise ConnectionError("nope")

    monkeypatch.setattr(dome_probe, "_READ_ONLY_PROPERTIES", ())  # irrelevant here

    import sys

    sys.modules["alpaca.dome"].Dome = _Boom  # type: ignore[attr-defined]

    runner = _make_runner()
    result = runner.invoke(
        cli.main,
        [
            "alpaca",
            "probe",
            "dome",
            "--host",
            "127.0.0.1",
            "--port",
            "1",
            "--output",
            str(tmp_path / "probe.json"),
        ],
    )
    assert result.exit_code != 0
    # ArcsecondError is not auto-rendered to stderr by Click; assert that the
    # CliRunner surfaces it as an exception rather than a stack trace from
    # somewhere deeper.
    assert isinstance(result.exception, BaseException)
    assert "Could not construct Alpaca Dome client" in str(result.exception)


def test_iter_probe_labels_covers_known_probes():
    labels = list(dome_probe.iter_probe_labels())
    assert "Connected" in labels
    assert "Name" in labels
    assert "SupportedActions" in labels
    assert any(label.startswith("CommandString(") for label in labels)
    assert any(label.startswith("CommandBool(") for label in labels)


# --------------------------------------------------------------------------- #
# Telescope                                                                    #
# --------------------------------------------------------------------------- #


class _EquatorialSystem(IntEnum):
    equOther = 0
    equTopocentric = 1
    equJ2000 = 2


class _DriveRates(IntEnum):
    driveSidereal = 0
    driveLunar = 1


class _FakeRate:
    """Stand-in for alpyca's ``Rate``: a range and nothing else."""

    def __init__(self, maxv: float, minv: float):
        self.Maximum = maxv
        self.Minimum = minv


class FakeTelescope:
    """
    Minimal stand-in for ``alpaca.telescope.Telescope``: a DFM-like mount
    that answers 0 for its optics, declares JNow, and can move two of its
    three axes. Any standard property not spelled out below reads as 0.0,
    the way an under-implemented driver answers.
    """

    Name = "FakeTelescope"
    Description = "A pretend mount for tests"
    DriverInfo = ["FakeTelescope 0.1"]
    DriverVersion = "0.1"
    InterfaceVersion = 3

    def __init__(self, address: str, device_number: int, protocol: str = "http"):
        self.address = address
        self.device_number = device_number
        self.protocol = protocol
        self.axis_rates_calls: list[int] = []
        self.command_blind_calls: list[tuple[str, bool]] = []
        self.command_string_calls: list[tuple[str, bool]] = []
        self.command_bool_calls: list[tuple[str, bool]] = []
        self.motion_invoked = False

    def __getattr__(self, name: str):
        if name[:1].isupper():
            return 0.0
        raise AttributeError(name)

    # --- the answers the tests look at -------------------------------------

    @property
    def Connected(self) -> bool:
        return True

    @property
    def EquatorialSystem(self) -> _EquatorialSystem:
        return _EquatorialSystem.equTopocentric

    @property
    def FocalLength(self) -> float:
        return 0.0

    @property
    def TrackingRates(self) -> list[_DriveRates]:
        return [_DriveRates.driveSidereal, _DriveRates.driveLunar]

    @property
    def UTCDate(self) -> datetime:
        return datetime(2026, 7, 29, 10, 49, 52, tzinfo=timezone.utc)

    @property
    def SiteElevation(self) -> float:
        raise _NotImplementedException(
            "SiteElevation is not implemented in this driver"
        )

    @property
    def SupportedActions(self) -> list[str]:
        return ["DFM:GetCapabilities"]

    # --- axes ----------------------------------------------------------------

    def CanMoveAxis(self, axis: int) -> bool:
        return axis in (0, 1)

    def AxisRates(self, axis: int) -> list[_FakeRate]:
        self.axis_rates_calls.append(axis)
        if axis == 2:
            raise RuntimeError("a real server would have died here")
        return [_FakeRate(maxv=4.0, minv=0.0)]

    # --- anything that moves the mount records the fact ----------------------

    def SlewToCoordinates(self, ra: float, dec: float) -> None:
        self.motion_invoked = True

    def MoveAxis(self, axis: int, rate: float) -> None:
        self.motion_invoked = True

    def Park(self) -> None:
        self.motion_invoked = True

    # --- passthroughs ----------------------------------------------------

    def CommandString(self, command: str, raw: bool = False) -> str:
        self.command_string_calls.append((command, raw))
        if command.startswith("XQ"):
            self.motion_invoked = True
        return f"FakeTelescope ack: {command}"

    def CommandBool(self, command: str, raw: bool = False) -> bool:
        self.command_bool_calls.append((command, raw))
        return False

    def CommandBlind(self, command: str, raw: bool = False) -> None:
        self.command_blind_calls.append((command, raw))
        self.motion_invoked = True


@pytest.fixture
def fake_telescope_factory():
    registry: list[FakeTelescope] = []

    def factory(address: str, device_number: int, protocol: str) -> FakeTelescope:
        scope = FakeTelescope(address, device_number, protocol)
        registry.append(scope)
        return scope

    return factory, registry


def test_probe_telescope_function_default_is_readonly(fake_telescope_factory):
    factory, registry = fake_telescope_factory

    result = probe_telescope(
        host="127.0.0.1",
        port=11111,
        device_number=0,
        protocol="http",
        telescope_factory=factory,
    )

    assert len(registry) == 1
    scope = registry[0]
    report = result.report

    # Section order: the axes sit with the device state, before the extension
    # surface.
    assert list(report)[:5] == [
        "environment",
        "device_metadata",
        "axes",
        "supported_actions",
        "command_passthrough",
    ]
    assert report["environment"]["device_type"] == "telescope"

    metadata = report["device_metadata"]
    assert metadata["Name"] == {"ok": True, "value": "FakeTelescope"}
    # The two answers that bit us in the field are written down verbatim,
    # not interpreted: a 0 focal length and a topocentric frame.
    assert metadata["FocalLength"] == {"ok": True, "value": 0.0}
    assert metadata["EquatorialSystem"]["value"] == {
        "name": "equTopocentric",
        "value": 1,
    }
    assert metadata["TrackingRates"]["value"] == [
        {"name": "driveSidereal", "value": 0},
        {"name": "driveLunar", "value": 1},
    ]
    assert metadata["UTCDate"]["value"] == "2026-07-29T10:49:52+00:00"
    assert metadata["SiteElevation"]["ok"] is False
    assert "_NotImplementedException" in metadata["SiteElevation"]["error"]
    # Every property in the list was asked for.
    assert set(metadata) == set(telescope_probe._READ_ONLY_PROPERTIES)

    # Axis rates only where the driver says the axis moves; the tertiary axis
    # is never asked, which is the guard that keeps a fragile server alive.
    axes = report["axes"]
    assert axes["primary"]["CanMoveAxis"]["value"] is True
    assert axes["primary"]["AxisRates"]["value"] == [{"minimum": 0.0, "maximum": 4.0}]
    assert axes["secondary"]["AxisRates"]["ok"] is True
    assert axes["tertiary"]["CanMoveAxis"]["value"] is False
    assert "AxisRates" not in axes["tertiary"]
    assert "not asked" in axes["tertiary"]["axis_rates_skipped_reason"]
    assert scope.axis_rates_calls == [0, 1]

    assert report["supported_actions"] == {"ok": True, "value": ["DFM:GetCapabilities"]}

    # Strictly read-only.
    assert scope.motion_invoked is False
    assert scope.command_blind_calls == []
    assert {cmd for cmd, _ in scope.command_string_calls} == {
        "MG TIME",
        "MG _BGA",
        "TE",
        "TP",
    }
    assert "command_blind_skipped_reason" in report["command_passthrough"]

    # Local target, so the host hints ride along.
    assert report["host_hints"]["collected_because"] == "target-is-local"

    assert result.counts.total > 0
    assert result.counts.ok < result.counts.total  # SiteElevation intentionally fails


def test_probe_telescope_function_allow_active_sends_blind(fake_telescope_factory):
    factory, registry = fake_telescope_factory

    probe_telescope(
        host="127.0.0.1",
        port=11111,
        protocol="http",
        allow_active=True,
        telescope_factory=factory,
    )

    scope = registry[0]
    assert (
        scope.command_blind_calls
    ), "CommandBlind should have been invoked under --allow-active"
    assert "XQ#STATUS" in {cmd for cmd, _ in scope.command_blind_calls}


def test_probe_telescope_axis_rates_failure_is_data(fake_telescope_factory):
    factory, registry = fake_telescope_factory

    class _Fragile(FakeTelescope):
        def CanMoveAxis(self, axis: int) -> bool:
            return True  # claims the tertiary axis too

    def fragile_factory(address, device_number, protocol):
        scope = _Fragile(address, device_number, protocol)
        registry.append(scope)
        return scope

    result = probe_telescope(
        host="127.0.0.1", port=11111, telescope_factory=fragile_factory
    )

    tertiary = result.report["axes"]["tertiary"]
    assert tertiary["CanMoveAxis"]["value"] is True
    assert tertiary["AxisRates"]["ok"] is False
    assert "RuntimeError" in tertiary["AxisRates"]["error"]


def test_cli_probe_telescope_writes_report(tmp_path, monkeypatch):
    runner = _make_runner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli.main,
        [
            "alpaca",
            "probe",
            "telescope",
            "--host",
            "127.0.0.1",
            "--port",
            "11111",
        ],
    )
    assert result.exit_code == 0, result.output
    written = list(tmp_path.glob("alpaca_telescope_probe_*.json"))
    assert len(written) == 1
    data = json.loads(written[0].read_text())
    assert data["environment"]["device_type"] == "telescope"
    assert set(data.keys()) >= {
        "environment",
        "device_metadata",
        "axes",
        "supported_actions",
        "command_passthrough",
        "host_hints",
    }
    assert "Alpaca telescope probe" in result.output
    assert "AxisRates(primary)" in result.output
    assert "SiteElevation" in result.output
    assert "Summary" in result.output


def test_cli_probe_telescope_fatal_connection_error_becomes_arcsecond_error(tmp_path):
    class _Boom(FakeTelescope):
        def __init__(self, *args, **kwargs):
            raise ConnectionError("nope")

    import sys

    sys.modules["alpaca.telescope"].Telescope = _Boom  # type: ignore[attr-defined]

    runner = _make_runner()
    result = runner.invoke(
        cli.main,
        [
            "alpaca",
            "probe",
            "telescope",
            "--host",
            "127.0.0.1",
            "--port",
            "1",
            "--output",
            str(tmp_path / "p.json"),
        ],
    )
    assert result.exit_code != 0
    assert "Could not construct Alpaca Telescope client" in str(result.exception)


def test_iter_probe_labels_telescope_covers_axes():
    labels = list(telescope_probe.iter_probe_labels())
    assert labels[0] == "Connected"
    assert "EquatorialSystem" in labels
    assert "CanMoveAxis(primary)" in labels
    assert "AxisRates(tertiary)" in labels
    assert labels.index("AxisRates(tertiary)") < labels.index("SupportedActions")
    assert any(label.startswith("CommandString(") for label in labels)
