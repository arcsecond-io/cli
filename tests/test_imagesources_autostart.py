"""The proxy's login item: the backends, and what `proxy start/stop` do with it."""

import plistlib
import sys

import pytest

from arcsecond.api.config import CONFIG_DIR_ENV_VAR
from arcsecond.imagesources import autostart


def test_the_login_command_is_a_plain_proxy_start_on_this_interpreter():
    command = autostart.login_command("0.0.0.0", 8765, "INFO")
    assert command[1:5] == ["-m", "arcsecond.cli", "proxy", "start"]
    assert "--foreground" not in command
    assert command[command.index("--port") + 1] == "8765"
    if sys.platform != "win32":
        assert command[0] == sys.executable


def test_the_environment_carries_the_overridden_config_dir():
    # conftest points ARCSECOND_CONFIG_DIR at a temp dir for the whole suite.
    assert CONFIG_DIR_ENV_VAR in autostart._environment()


def test_the_backend_follows_the_platform(monkeypatch):
    monkeypatch.setattr(autostart.sys, "platform", "win32")
    assert isinstance(autostart.backend(), autostart.WindowsRunKey)
    monkeypatch.setattr(autostart.sys, "platform", "darwin")
    assert isinstance(autostart.backend(), autostart.LaunchAgent)
    monkeypatch.setattr(autostart.sys, "platform", "linux")
    assert isinstance(autostart.backend(), autostart.SystemdUserUnit)


def test_launch_agent_fires_once_at_login_and_never_supervises(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart.subprocess, "run", lambda *a, **k: None)
    agent = autostart.LaunchAgent(tmp_path / "agents" / "proxy.plist")
    assert agent.is_enabled() is False

    agent.enable(
        ["python", "-m", "arcsecond.cli", "proxy", "start"],
        {"ARCSECOND_CONFIG_DIR": "/cfg"},
    )
    assert agent.is_enabled() is True
    payload = plistlib.loads(agent.path.read_bytes())
    assert payload["Label"] == autostart.LABEL
    assert payload["ProgramArguments"][-2:] == ["proxy", "start"]
    assert payload["RunAtLoad"] is True
    assert "KeepAlive" not in payload
    assert payload["EnvironmentVariables"] == {"ARCSECOND_CONFIG_DIR": "/cfg"}

    agent.disable()
    assert agent.is_enabled() is False
    agent.disable()  # a second time is not an error


def test_systemd_unit_is_a_oneshot_wanted_at_login(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        autostart.SystemdUserUnit,
        "_systemctl",
        staticmethod(lambda *a: calls.append(a)),
    )
    unit = autostart.SystemdUserUnit(tmp_path / "user" / autostart.SYSTEMD_UNIT)

    unit.enable(
        ["/opt/py thon", "-m", "arcsecond.cli", "proxy", "start"],
        {"ARCSECOND_CONFIG_DIR": "/c fg"},
    )
    text = unit.path.read_text()
    assert "Type=oneshot" in text
    assert "ExecStart='/opt/py thon' -m arcsecond.cli proxy start" in text
    assert "Environment='ARCSECOND_CONFIG_DIR=/c fg'" in text
    assert "WantedBy=default.target" in text
    assert calls == [("daemon-reload",), ("enable", autostart.SYSTEMD_UNIT)]

    unit.disable()
    assert not unit.path.exists()
    assert calls[2] == ("disable", autostart.SYSTEMD_UNIT)


@pytest.mark.skipif(
    sys.platform != "win32", reason="the registry only exists on Windows"
)
def test_windows_run_key_round_trips():
    key = autostart.WindowsRunKey("ArcsecondLiveImageProxyTest")
    try:
        key.enable(["C:\\py\\pythonw.exe", "-m", "arcsecond.cli", "proxy", "start"], {})
        assert key.is_enabled()
    finally:
        key.disable()
    assert not key.is_enabled()


def test_a_backend_failure_becomes_a_reportable_error(monkeypatch):
    class Broken:
        def enable(self, command, environment):
            raise OSError("read-only file system")

        def is_enabled(self):
            raise OSError("nope")

        def disable(self):
            pass

        def describe(self):
            return "broken"

    monkeypatch.setattr(autostart, "backend", lambda: Broken())
    with pytest.raises(autostart.AutostartError, match="read-only"):
        autostart.enable("0.0.0.0", 8765, "INFO")
    assert autostart.is_enabled() is False
