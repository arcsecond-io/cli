"""
Tests for the ``arcsecond alpaca probe dome`` CLI command.

The real ASCOM Alpaca server is replaced with a stub ``FakeDome`` so the
suite runs offline. We exercise the CLI through ``click.testing.CliRunner``
to cover both the probe logic and the Click wiring.
"""

from __future__ import annotations

import json
from enum import IntEnum

import pytest
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.alpaca import dome_probe
from arcsecond.alpaca.dome_probe import probe_dome


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
    sys.modules["alpaca"] = alpaca_pkg
    sys.modules["alpaca.dome"] = dome_mod
    yield
    sys.modules.pop("alpaca", None)
    sys.modules.pop("alpaca.dome", None)


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
    assert "host_hints" not in result.report

    # Environment captures connectivity.
    env = result.report["environment"]
    assert env["host"] == "127.0.0.1"
    assert env["port"] == 11111
    assert env["device_number"] == 0
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


def test_probe_dome_function_collect_host_info_adds_section(fake_dome_factory):
    factory, _ = fake_dome_factory

    result = probe_dome(
        host="127.0.0.1",
        port=11111,
        protocol="http",
        collect_host_info=True,
        dome_factory=factory,
    )
    assert "host_hints" in result.report
    assert "os" in result.report["host_hints"]


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
    # Default invocation: no host_hints, no CommandBlind block populated.
    assert "host_hints" not in data
    assert data["command_passthrough"]["command_blind"] == []
    assert data["command_passthrough"]["command_blind_skipped_reason"].startswith(
        "CommandBlind is fire-and-forget"
    )


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
