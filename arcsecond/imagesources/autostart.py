"""Bring the live-image proxy back after a reboot.

The Docker side of Arcsecond.local survives a reboot on its own — every
container is `restart: unless-stopped`, so Docker brings the stack back when it
starts at login. The proxy is a detached host process with no supervisor, so
it would not, and an observatory whose cameras vanish after every power cut is
not a usable observatory.

The rule is the simplest one that gives the right answer: a proxy that was
running when the machine went down comes back; one that was stopped stays
stopped. It is implemented without any state of its own — `proxy start`
registers a per-user login item, `proxy stop` removes it, and the item's
presence *is* "it was running". A crash, a kill or a power cut leaves the item
in place, so the proxy returns; a deliberate stop takes it away.

The item runs the very command `proxy start` uses to detach — this
interpreter, `-m arcsecond.cli proxy start` — so the proxy that comes back at
login is the one that was configured, on the same Python. `proxy start` is
idempotent (a running proxy is reported, not doubled), so a machine that never
went down is not disturbed by the item firing again.

Per platform, all user-level, none needing administrator rights:

  Windows   HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run — a plain
            "run this at login" value. Not Task Scheduler, whose ONLOGON
            trigger wants elevation on most machines.
  macOS     a LaunchAgent plist with RunAtLoad and *no* KeepAlive: launchd
            fires the command once at login and does not become a second
            supervisor fighting `proxy stop`.
  Linux     a systemd --user oneshot unit, enabled. A headless machine has to
            allow user services to run without a session:
            `loginctl enable-linger $USER`.
"""

import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

from arcsecond.api.config import CONFIG_DIR_ENV_VAR, ArcsecondConfig

LABEL = "io.arcsecond.live-image-proxy"
WINDOWS_VALUE_NAME = "ArcsecondLiveImageProxy"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
SYSTEMD_UNIT = "arcsecond-live-image-proxy.service"


def _interpreter() -> str:
    """The Python to run at login. On Windows, the windowless twin of this
    interpreter when it exists, so no console flashes up at logon."""
    executable = sys.executable
    if sys.platform == "win32":
        head, tail = os.path.split(executable)
        if tail.lower() == "python.exe":
            windowless = os.path.join(head, "pythonw.exe")
            if os.path.exists(windowless):
                return windowless
    return executable


def login_command(host: str, port: int, log_level: str) -> list:
    """What to run at login. No --foreground: the CLI detaches the proxy
    exactly as `proxy start` typed in a terminal would, then exits."""
    return [
        _interpreter(),
        "-m",
        "arcsecond.cli",
        "proxy",
        "start",
        "--host",
        str(host),
        "--port",
        str(port),
        "--log-level",
        str(log_level),
    ]


def _environment() -> dict:
    """The proxy must find the same configuration directory as the command
    that registered it, so an overridden ARCSECOND_CONFIG_DIR travels along."""
    if ArcsecondConfig.is_dir_path_overridden():
        return {CONFIG_DIR_ENV_VAR: str(ArcsecondConfig.dir_path())}
    return {}


class AutostartError(Exception):
    pass


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


class WindowsRunKey:
    def __init__(self, value_name: str = WINDOWS_VALUE_NAME):
        self.value_name = value_name

    def enable(self, command: list, environment: dict) -> None:
        import winreg  # only importable on Windows

        quoted = subprocess.list2cmdline(command)
        if environment:
            # A Run value is one command line, with no environment of its own.
            assignments = " && ".join(f"set {k}={v}" for k, v in environment.items())
            quoted = f'cmd.exe /c "{assignments} && {quoted}"'
        # CreateKeyEx, not OpenKey: the Run key is absent from a profile that
        # never had a login item (a fresh account, a CI runner), and opening
        # what does not exist is a FileNotFoundError.
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, self.value_name, 0, winreg.REG_SZ, quoted)

    def disable(self) -> None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, self.value_name)
        except FileNotFoundError:
            pass  # no key, or no value: nothing registered

    def is_enabled(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_READ
            ) as key:
                winreg.QueryValueEx(key, self.value_name)
                return True
        except FileNotFoundError:
            return False

    def describe(self) -> str:
        return f"a Run entry in the registry ({self.value_name})"


class LaunchAgent:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or (
            Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        )

    def enable(self, command: list, environment: dict) -> None:
        payload = {
            "Label": LABEL,
            "ProgramArguments": list(command),
            "RunAtLoad": True,
            # No KeepAlive on purpose: fire once at login, then stay out of it.
        }
        if environment:
            payload["EnvironmentVariables"] = dict(environment)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(plistlib.dumps(payload))

    def disable(self) -> None:
        # Unload it too, best effort, so that a logout/login cycle is not
        # needed for launchd to forget it. The file going away is what counts.
        if self.path.exists():
            # os.getuid does not exist on Windows; the backend does not run
            # there, but its tests do.
            getuid = getattr(os, "getuid", None)
            if getuid is not None:
                subprocess.run(
                    ["launchctl", "bootout", f"gui/{getuid()}/{LABEL}"],
                    capture_output=True,
                    check=False,
                )
            self.path.unlink()

    def is_enabled(self) -> bool:
        return self.path.exists()

    def describe(self) -> str:
        return f"a LaunchAgent ({self.path})"


class SystemdUserUnit:
    def __init__(self, path: Optional[Path] = None):
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        self.path = path or (base / "systemd" / "user" / SYSTEMD_UNIT)

    def enable(self, command: list, environment: dict) -> None:
        lines = [
            "[Unit]",
            "Description=Arcsecond live-image proxy (started at login by the arcsecond CLI)",
            "After=network-online.target",
            "",
            "[Service]",
            "Type=oneshot",
            "ExecStart=" + " ".join(shlex.quote(part) for part in command),
        ]
        for key, value in environment.items():
            lines.append(f"Environment={shlex.quote(f'{key}={value}')}")
        lines += ["", "[Install]", "WantedBy=default.target", ""]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(lines), encoding="utf-8")
        self._systemctl("daemon-reload")
        self._systemctl("enable", SYSTEMD_UNIT)

    def disable(self) -> None:
        if self.path.exists():
            self._systemctl("disable", SYSTEMD_UNIT)
            self.path.unlink()
            self._systemctl("daemon-reload")

    def is_enabled(self) -> bool:
        return self.path.exists()

    def describe(self) -> str:
        return f"a systemd user unit ({self.path})"

    @staticmethod
    def _systemctl(*args) -> None:
        try:
            subprocess.run(
                ["systemctl", "--user", *args], capture_output=True, check=False
            )
        except FileNotFoundError:
            pass  # no systemd: the unit file is still there for one that appears


def backend():
    if sys.platform == "win32":
        return WindowsRunKey()
    if sys.platform == "darwin":
        return LaunchAgent()
    return SystemdUserUnit()


# ---------------------------------------------------------------------------
# What the proxy commands call
# ---------------------------------------------------------------------------


def enable(host: str, port: int, log_level: str) -> str:
    """Register the login item. Returns a description of it, for the operator."""
    item = backend()
    try:
        item.enable(login_command(host, port, log_level), _environment())
    except OSError as e:
        raise AutostartError(str(e)) from e
    return item.describe()


def disable() -> bool:
    """Remove the login item. True if there was one."""
    item = backend()
    try:
        if not item.is_enabled():
            return False
        item.disable()
        return True
    except OSError as e:
        raise AutostartError(str(e)) from e


def is_enabled() -> bool:
    try:
        return backend().is_enabled()
    except OSError:
        return False
