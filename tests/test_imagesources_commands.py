"""Tests for the camera commands themselves.

These cover the shape of the CLI rather than the plumbing underneath: that
listing does not probe, that detection does not register, that the id printed
is the id accepted, and that `forget` works for every kind of camera. Each of
those was broken or impossible before, so each is asserted end to end through
the Click runner rather than against the store alone.
"""

import signal
import sys

import pytest
from click.testing import CliRunner

from arcsecond.imagesources import commands, runtime, store
from arcsecond.imagesources.commands import allsky, netcam, proxy, webcam
from arcsecond.imagesources.sources.base import DetectedDevice


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """A runner whose store is a temp file and whose proxy is never running.

    Launching is blocked outright. `proxy start` now puts a real background
    process on a real port, and a test that reaches that code path by accident
    leaves one running on the machine long after pytest has exited — which is
    exactly what happened once while this was being written. Tests that mean to
    exercise the launch use the `launched` fixture, which replaces this.
    """
    monkeypatch.setattr(store, "store_path", lambda: tmp_path / "cameras.json")
    monkeypatch.setattr(runtime, "runtime_path", lambda: tmp_path / "proxy.json")
    monkeypatch.setattr(runtime, "log_path", lambda: tmp_path / "proxy.log")
    monkeypatch.setattr(commands, "_running_proxy_port", lambda: None)

    def no_real_processes(command, **kwargs):
        raise AssertionError(
            f"a test tried to launch a real background proxy: {command}"
        )

    monkeypatch.setattr(commands.subprocess, "Popen", no_real_processes)
    return CliRunner()


def _no_webcams(monkeypatch):
    monkeypatch.setattr(
        "arcsecond.imagesources.sources.opencv.detect_webcams", lambda *a, **k: []
    )


def _run(cli, group, args):
    result = cli.invoke(group, args)
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        result.output,
        result.exception,
    )
    return result


# ---------------------------------------------------------------------------
# The naked commands list, and do not detect
# ---------------------------------------------------------------------------


def test_bare_webcam_lists_without_probing(cli, monkeypatch):
    def explode(*a, **k):
        raise AssertionError("detection ran")

    monkeypatch.setattr("arcsecond.imagesources.sources.opencv.detect_webcams", explode)
    monkeypatch.setattr(
        "arcsecond.imagesources.sources.filewatch.detect_allsky", explode
    )
    result = _run(cli, webcam, [])
    assert "No webcam is registered" in result.output


def test_bare_allsky_lists_without_probing(cli, monkeypatch):
    def explode(*a, **k):
        raise AssertionError("detection ran")

    monkeypatch.setattr(
        "arcsecond.imagesources.sources.filewatch.detect_allsky", explode
    )
    result = _run(cli, allsky, [])
    assert "No all-sky camera is registered" in result.output


def test_bare_webcam_lists_both_kinds_of_webcam(cli, monkeypatch):
    _no_webcams(monkeypatch)
    _run(cli, webcam, ["add", "0"])
    _run(cli, webcam, ["add", "rtsp://cam.local/s"])
    result = _run(cli, webcam, [])
    assert "device index 0" in result.output
    assert "rtsp://cam.local/s" in result.output
    assert "Registered webcams (2)" in result.output


def test_bare_webcam_does_not_list_all_sky_cameras(cli, monkeypatch):
    _no_webcams(monkeypatch)
    _run(cli, allsky, ["add", "/srv/sky.jpg"])
    assert "/srv/sky.jpg" not in _run(cli, webcam, []).output


def test_a_listed_password_is_redacted(cli, monkeypatch):
    monkeypatch.setenv("PW", "hunter2")
    _run(cli, webcam, ["add", "rtsp://admin:${PW}@cam.local/s"])
    assert "hunter2" not in _run(cli, webcam, []).output


# ---------------------------------------------------------------------------
# detect only detects
# ---------------------------------------------------------------------------


def test_detect_does_not_register_what_it_finds(cli, monkeypatch):
    device = DetectedDevice(
        kind="usb", identity=("usb", 0), label="USB webcam #0", extra={"index": 0}
    )
    monkeypatch.setattr(
        "arcsecond.imagesources.sources.opencv.detect_webcams", lambda *a, **k: [device]
    )
    result = _run(cli, webcam, ["detect", "--no-network"])
    assert "Newly detected" in result.output
    # Nothing was registered by looking.
    assert "No webcam is registered" in _run(cli, webcam, []).output


def test_detect_tells_you_the_command_that_registers_what_it_found(cli, monkeypatch):
    device = DetectedDevice(
        kind="usb", identity=("usb", 2), label="USB webcam #2", extra={"index": 2}
    )
    monkeypatch.setattr(
        "arcsecond.imagesources.sources.opencv.detect_webcams", lambda *a, **k: [device]
    )
    assert (
        "arcsecond webcam add 2" in _run(cli, webcam, ["detect", "--no-network"]).output
    )


def test_detect_separates_the_three_answers(cli, monkeypatch):
    device = DetectedDevice(
        kind="usb", identity=("usb", 1), label="USB webcam #1", extra={"index": 1}
    )
    monkeypatch.setattr(
        "arcsecond.imagesources.sources.opencv.detect_webcams", lambda *a, **k: [device]
    )
    _run(cli, webcam, ["add", "1"])  # present
    _run(cli, webcam, ["add", "7"])  # registered, not attached
    output = _run(cli, webcam, ["detect", "--no-network"]).output
    assert "Registered and present (1)" in output
    assert "Registered but not found (1)" in output


def test_a_missing_camera_stays_registered(cli, monkeypatch):
    _no_webcams(monkeypatch)
    _run(cli, webcam, ["add", "7"])
    _run(cli, webcam, ["detect", "--no-network"])
    assert "device index 7" in _run(cli, webcam, []).output


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


def test_add_prints_the_id_you_will_need_later(cli, monkeypatch):
    _no_webcams(monkeypatch)
    result = _run(cli, webcam, ["add", "0"])
    printed = result.output.split("Registered ")[1].split()[0]
    assert store.find(printed) is not None


def test_the_id_that_is_printed_is_the_id_forget_accepts(cli, monkeypatch):
    """The mismatch that made `forget` unusable."""
    _no_webcams(monkeypatch)
    printed = _run(cli, webcam, ["add", "0"]).output.split("Registered ")[1].split()[0]
    assert "Forgotten" in _run(cli, webcam, ["forget", printed]).output
    assert store.find(printed) is None


def test_adding_the_same_camera_twice_does_not_duplicate_it(cli, monkeypatch):
    _no_webcams(monkeypatch)
    _run(cli, webcam, ["add", "0"])
    result = _run(cli, webcam, ["add", "0"])
    assert "Already registered" in result.output
    assert len(store.all_cameras()) == 1


def test_a_path_given_to_webcam_add_points_at_allsky(cli):
    result = _run(cli, webcam, ["add", "/srv/allsky/latest.jpg"])
    assert result.exit_code == 1
    assert "arcsecond allsky add" in result.output


def test_an_address_given_to_allsky_add_points_at_webcam(cli):
    result = _run(cli, allsky, ["add", "rtsp://cam.local/s"])
    assert result.exit_code == 1
    assert "arcsecond webcam add" in result.output


def test_an_unsupported_scheme_is_refused(cli):
    result = _run(cli, webcam, ["add", "ftp://cam.local/s"])
    assert result.exit_code == 1
    assert "rtsp://" in result.output


def test_a_password_is_never_written_in_the_clear(cli, monkeypatch, tmp_path):
    monkeypatch.setenv("PW", "hunter2")
    _run(cli, webcam, ["add", "rtsp://admin:${PW}@cam.local/s"])
    written = (tmp_path / "cameras.json").read_text()
    assert "${PW}" in written
    assert "hunter2" not in written


def test_a_missing_variable_is_reported_before_anything_is_registered(cli, monkeypatch):
    monkeypatch.delenv("PW", raising=False)
    result = cli.invoke(webcam, ["add", "rtsp://admin:${PW}@cam.local/s"])
    assert result.exit_code != 0
    assert "PW" in result.output
    assert store.all_cameras() == []


# ---------------------------------------------------------------------------
# forget
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "group,add_args",
    [
        (webcam, ["add", "0"]),
        (webcam, ["add", "rtsp://c/s"]),
        (allsky, ["add", "/a.jpg"]),
    ],
)
def test_forget_works_for_every_kind_of_camera(cli, monkeypatch, group, add_args):
    _no_webcams(monkeypatch)
    printed = _run(cli, group, add_args).output.split("Registered ")[1].split()[0]
    assert "Forgotten" in _run(cli, group, ["forget", printed]).output
    assert store.all_cameras() == []


def test_forget_takes_no_port_option(cli):
    """The proxy is found by itself — see runtime.py."""
    result = cli.invoke(webcam, ["forget", "abc", "--port", "8765"])
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


def test_allsky_forget_takes_no_port_option(cli):
    result = cli.invoke(allsky, ["forget", "abc", "--port", "8765"])
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


def test_forgetting_the_wrong_kind_names_the_command_that_works(cli):
    printed = (
        _run(cli, allsky, ["add", "/a.jpg"]).output.split("Registered ")[1].split()[0]
    )
    result = _run(cli, webcam, ["forget", printed])
    assert result.exit_code == 1
    assert f"arcsecond allsky forget {printed}" in result.output
    # And it is still registered — a refusal must not half-delete anything.
    assert store.find(printed) is not None


def test_forgetting_an_unknown_id_says_where_to_look(cli):
    result = _run(cli, webcam, ["forget", "zzz"])
    assert result.exit_code == 1
    assert "arcsecond webcam" in result.output


def test_forget_tells_a_running_proxy(cli, monkeypatch):
    _no_webcams(monkeypatch)
    printed = _run(cli, webcam, ["add", "0"]).output.split("Registered ")[1].split()[0]

    told = []
    monkeypatch.setattr(
        commands, "_tell_proxy_to_forget", lambda i: told.append(i) or True
    )
    _run(cli, webcam, ["forget", printed])
    assert told == [printed]


# ---------------------------------------------------------------------------
# Registering and starting are separate
# ---------------------------------------------------------------------------


def test_add_never_starts_a_proxy(cli, monkeypatch):
    _no_webcams(monkeypatch)
    monkeypatch.setattr(
        "arcsecond.imagesources.proxy.run",
        lambda **k: (_ for _ in ()).throw(AssertionError("proxy started")),
    )
    _run(cli, webcam, ["add", "0"])


def test_proxy_start_never_registers_anything(cli, monkeypatch):
    started = {}
    monkeypatch.setattr(
        "arcsecond.imagesources.proxy.run", lambda **k: started.update(k)
    )
    _run(cli, proxy, ["start", "--foreground"])
    assert started["cameras"] == []
    assert store.all_cameras() == []


def test_proxy_start_serves_every_registered_camera(cli, monkeypatch):
    _no_webcams(monkeypatch)
    _run(cli, webcam, ["add", "0"])
    _run(cli, webcam, ["add", "rtsp://cam.local/s"])
    _run(cli, allsky, ["add", "/a.jpg"])

    started = {}
    monkeypatch.setattr(
        "arcsecond.imagesources.proxy.run", lambda **k: started.update(k)
    )
    _run(cli, proxy, ["start", "--foreground"])
    assert {c.kind for c in started["cameras"]} == {"usb", "net", "allsky"}


def test_proxy_start_hands_the_expanded_url_to_the_proxy(cli, monkeypatch):
    """The store keeps ${VAR}; the proxy needs the real thing."""
    monkeypatch.setenv("PW", "hunter2")
    _run(cli, webcam, ["add", "rtsp://admin:${PW}@cam.local/s"])

    started = {}
    monkeypatch.setattr(
        "arcsecond.imagesources.proxy.run", lambda **k: started.update(k)
    )
    _run(cli, proxy, ["start", "--foreground"])
    assert started["cameras"][0].url == "rtsp://admin:hunter2@cam.local/s"


def test_proxy_start_refuses_a_second_proxy(cli, monkeypatch):
    monkeypatch.setattr(commands, "_running_proxy_port", lambda: 8765)
    monkeypatch.setattr(
        "arcsecond.imagesources.proxy.run",
        lambda **k: (_ for _ in ()).throw(AssertionError("started anyway")),
    )
    result = _run(cli, proxy, ["start", "--foreground"])
    assert result.exit_code == 1
    assert "already running on port 8765" in result.output


# ---------------------------------------------------------------------------
# What was removed says where it went
# ---------------------------------------------------------------------------


def test_webcam_start_points_at_add_and_proxy_start(cli):
    result = _run(cli, webcam, ["start", "--netcam", "dome=rtsp://cam.local/s"])
    assert result.exit_code == 1
    assert "arcsecond webcam add" in result.output
    assert "arcsecond proxy start" in result.output


def test_allsky_start_points_at_add_and_proxy_start(cli):
    result = _run(cli, allsky, ["start", "--allsky", "roof=/a.jpg"])
    assert result.exit_code == 1
    assert "arcsecond allsky add" in result.output
    assert "arcsecond proxy start" in result.output


def test_netcam_points_at_webcam(cli):
    result = _run(cli, netcam, ["test", "rtsp://cam.local/s"])
    assert result.exit_code == 1
    assert "arcsecond webcam" in result.output


@pytest.mark.parametrize("group", [webcam, allsky])
def test_the_removed_start_is_hidden_from_help(cli, group):
    assert "start" not in _run(cli, group, ["--help"]).output


# ---------------------------------------------------------------------------
# proxy status
# ---------------------------------------------------------------------------


def test_status_says_so_when_nothing_is_running(cli):
    result = _run(cli, proxy, ["status"])
    assert "not running" in result.output
    assert "arcsecond proxy start" in result.output


def test_status_reports_what_a_running_proxy_serves(cli, monkeypatch):
    monkeypatch.setattr(commands, "_running_proxy_port", lambda: 9911)
    monkeypatch.setattr(
        commands,
        "_call_proxy",
        lambda port, path, **k: [
            {
                "id": "abc",
                "kind": "webcam",
                "label": "Dome",
                "extra": {"transport": "rtsp", "url": "rtsp://cam.local/s"},
            }
        ],
    )
    result = _run(cli, proxy, ["status"])
    assert "running on port 9911" in result.output
    assert "abc" in result.output
    assert "rtsp://cam.local/s" in result.output


# ---------------------------------------------------------------------------
# Starting in the background
#
# The proxy is a service the Arcsecond containers talk to, so `start` hands the
# terminal back and `stop` ends it from anywhere. A proxy you could only end
# with Ctrl-C in one particular window would make `stop` and `status` largely
# decorative.
# ---------------------------------------------------------------------------


class FakePopen:
    """A background proxy that comes up, or does not, on command."""

    def __init__(self, command, returncode=None, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.pid = 4711
        self._returncode = returncode
        self.returncode = None
        self.killed = False

    def poll(self):
        self.returncode = self._returncode
        return self._returncode

    def kill(self):
        self.killed = True


@pytest.fixture
def launched(cli, monkeypatch, tmp_path):
    """Capture the background launch instead of really starting a proxy."""
    monkeypatch.setattr(runtime, "log_path", lambda: tmp_path / "proxy.log")
    started = {}

    def fake_popen(command, **kwargs):
        started["process"] = FakePopen(command, **kwargs)
        return started["process"]

    monkeypatch.setattr(commands.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        commands, "_proxy_is_running", lambda port: "process" in started
    )
    return started


def test_start_returns_the_prompt_instead_of_holding_the_terminal(
    cli, launched, monkeypatch
):
    monkeypatch.setattr(
        "arcsecond.imagesources.proxy.run",
        lambda **k: (_ for _ in ()).throw(AssertionError("ran in the foreground")),
    )
    result = _run(cli, proxy, ["start"])
    assert result.exit_code == 0
    assert "The proxy is running" in result.output
    assert "arcsecond proxy stop" in result.output


def test_start_launches_the_proxy_on_this_very_interpreter(cli, launched):
    _run(cli, proxy, ["start", "--port", "9000"])
    command = launched["process"].command
    assert command[0] == sys.executable
    assert command[1:5] == ["-m", "arcsecond.cli", "proxy", "start"]
    assert "--foreground" in command
    assert command[command.index("--port") + 1] == "9000"


def test_the_background_proxy_outlives_the_terminal_that_started_it(cli, launched):
    _run(cli, proxy, ["start"])
    kwargs = launched["process"].kwargs
    if sys.platform == "win32":
        assert kwargs["creationflags"]
    else:
        # Its own session, so closing the terminal does not take it down.
        assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] is commands.subprocess.DEVNULL


def test_start_says_where_the_background_proxy_writes_its_log(cli, launched, tmp_path):
    result = _run(cli, proxy, ["start"])
    assert str(tmp_path / "proxy.log") in result.output


def test_foreground_runs_here_and_launches_nothing(cli, monkeypatch):
    def no_launching(*a, **k):
        raise AssertionError("launched a background proxy")

    monkeypatch.setattr(commands.subprocess, "Popen", no_launching)
    ran = {}
    monkeypatch.setattr("arcsecond.imagesources.proxy.run", lambda **k: ran.update(k))
    result = _run(cli, proxy, ["start", "--foreground"])
    assert ran["port"] == 8765
    assert "Press Ctrl-C to stop" in result.output


def test_the_background_proxy_is_told_not_to_repeat_the_summary(cli, launched):
    """Its parent already printed it; in the log it would bury the next error."""
    _run(cli, proxy, ["start"])
    assert "--no-banner" in launched["process"].command


def test_a_background_proxy_that_dies_is_reported_not_called_a_success(
    cli, monkeypatch, tmp_path
):
    log = tmp_path / "proxy.log"
    log.write_text("Error: port 8765 is already taken by something else.\n")
    monkeypatch.setattr(runtime, "log_path", lambda: log)
    monkeypatch.setattr(
        commands.subprocess, "Popen", lambda c, **k: FakePopen(c, returncode=1, **k)
    )
    monkeypatch.setattr(commands, "_proxy_is_running", lambda port: False)

    result = _run(cli, proxy, ["start"])
    assert result.exit_code == 1
    assert "would not start" in result.output
    # Its own last words, so the reason is on screen and not only in a file.
    assert "already taken" in result.output


def test_a_background_proxy_that_never_answers_is_not_left_running(
    cli, monkeypatch, tmp_path
):
    monkeypatch.setattr(runtime, "log_path", lambda: tmp_path / "proxy.log")
    process = FakePopen(["python"], returncode=None)
    monkeypatch.setattr(commands.subprocess, "Popen", lambda c, **k: process)
    monkeypatch.setattr(commands, "_proxy_is_running", lambda port: False)
    monkeypatch.setattr(commands, "START_TIMEOUT", 0.0)

    result = _run(cli, proxy, ["start"])
    assert result.exit_code == 1
    assert process.killed is True


# ---------------------------------------------------------------------------
# proxy stop
# ---------------------------------------------------------------------------


@pytest.fixture
def signalled(monkeypatch):
    """Record what `stop` signals, without signalling anything."""
    sent = []
    monkeypatch.setattr(commands.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    return sent


def test_stop_says_so_when_nothing_is_running(cli, monkeypatch):
    monkeypatch.setattr(commands, "_running_proxy", lambda: None)
    result = _run(cli, proxy, ["stop"])
    assert result.exit_code == 0
    assert "not running" in result.output


def test_stop_asks_the_proxy_to_go_before_insisting(cli, monkeypatch, signalled):
    monkeypatch.setattr(commands, "_running_proxy", lambda: (8765, 4711))
    monkeypatch.setattr(commands, "_has_exited", lambda port, pid: True)
    result = _run(cli, proxy, ["stop"])
    assert result.exit_code == 0
    assert "Stopped." in result.output
    assert signalled == [(4711, signal.SIGTERM)]


def test_stop_insists_when_asking_did_not_work(cli, monkeypatch, signalled):
    monkeypatch.setattr(commands, "_running_proxy", lambda: (8765, 4711))
    monkeypatch.setattr(commands, "_has_exited", lambda port, pid: False)
    monkeypatch.setattr(commands, "_HARD_TIMEOUT", 0.0)
    result = _run(cli, proxy, ["stop", "--timeout", "0"])
    assert result.exit_code == 1
    assert [sig for _, sig in signalled] == [signal.SIGTERM, commands._HARD_SIGNAL]


def test_stop_signals_the_pid_the_proxy_gave_not_the_one_on_disk(cli, monkeypatch):
    """A runtime note outlives a killed proxy; by then its pid may be anyone's."""
    monkeypatch.setattr(runtime, "read", lambda path=None: {"port": 8765, "pid": 111})
    monkeypatch.setattr(
        commands, "_proxy_health", lambda port: {"status": "ok", "pid": 999}
    )
    assert commands._running_proxy() == (8765, 999)


def test_a_proxy_that_will_not_say_its_pid_is_not_guessed_at(cli, monkeypatch):
    monkeypatch.setattr(commands, "_running_proxy", lambda: (8765, None))
    result = _run(cli, proxy, ["stop"])
    assert result.exit_code == 1
    assert "Ctrl-C" in result.output


def test_stop_treats_an_already_gone_proxy_as_stopped(cli, monkeypatch):
    monkeypatch.setattr(commands, "_running_proxy", lambda: (8765, 4711))

    def already_gone(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(commands.os, "kill", already_gone)
    result = _run(cli, proxy, ["stop"])
    assert result.exit_code == 0
    assert "Stopped." in result.output


def test_stop_does_not_pretend_it_can_end_another_users_proxy(cli, monkeypatch):
    monkeypatch.setattr(commands, "_running_proxy", lambda: (8765, 4711))

    def not_yours(pid, sig):
        raise PermissionError()

    monkeypatch.setattr(commands.os, "kill", not_yours)
    result = _run(cli, proxy, ["stop"])
    assert result.exit_code == 1
    assert "another user" in result.output


def test_stop_leaves_the_registered_cameras_alone(cli, monkeypatch, signalled):
    _run(cli, allsky, ["add", "/a.jpg"])
    monkeypatch.setattr(commands, "_running_proxy", lambda: (8765, 4711))
    monkeypatch.setattr(commands, "_has_exited", lambda port, pid: True)
    _run(cli, proxy, ["stop"])
    assert len(store.all_cameras()) == 1


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal semantics")
def test_a_proxy_is_only_stopped_once_its_process_is_gone(monkeypatch):
    """Not once the port goes quiet: aiohttp closes the socket first, and the
    cameras are still open for a moment after that."""
    monkeypatch.setattr(commands, "_proxy_is_running", lambda port: False)

    alive = {"gone": False}

    def kill(pid, sig):
        if alive["gone"]:
            raise ProcessLookupError()

    monkeypatch.setattr(commands.os, "kill", kill)
    assert commands._has_exited(8765, 4711) is False
    alive["gone"] = True
    assert commands._has_exited(8765, 4711) is True
