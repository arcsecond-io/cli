"""Characterization tests for the restore path.

`_restore_dump` streams a dump into psql and interprets what comes back. Its
error handling is subtle — a write failure usually means psql has already
exited, and the return code is the honest account of why — so these pin the
behaviour rather than describe it, and exist mainly so the function can be
changed without silently changing what a failed restore does.

No Docker and no psql: the process is a stand-in, which is enough because
everything asserted here is about how its exit code, stderr and broken stdin
are interpreted.
"""

import subprocess
from importlib import import_module
from unittest.mock import patch

import pytest

# The module, not the click Group of the same name: hosting/__init__.py
# re-exports the Group, which shadows the submodule as a package attribute, so
# plain `import arcsecond.hosting.backups as backups` hands back the Group.
backups = import_module("arcsecond.hosting.backups")


class FakeStream:
    def __init__(self, data=b"", raises=None):
        self._data = data
        self._raises = raises
        self.closed = False
        self.written = []

    def write(self, chunk):
        if self._raises is not None:
            raise self._raises
        self.written.append(chunk)

    def read(self):
        if self._raises is not None:
            raise self._raises
        return self._data

    def close(self):
        self.closed = True


class FakePsql:
    """Enough of Popen to exercise the interpretation, and nothing more."""

    def __init__(self, returncode=0, stderr=b"", write_raises=None, hangs=False):
        self.stdin = FakeStream(raises=write_raises)
        self.stderr = FakeStream(data=stderr)
        self._returncode = returncode
        self._hangs = hangs
        self.killed = False
        self.waits = []
        self._finished = False

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self._hangs and not self.killed:
            raise subprocess.TimeoutExpired(cmd="psql", timeout=timeout)
        self._finished = True
        return self._returncode

    def kill(self):
        self.killed = True

    def poll(self):
        return self._returncode if self._finished else None


@pytest.fixture
def psql_env(monkeypatch, tmp_path):
    monkeypatch.setattr(backups, "_read_env_value", lambda key: "x")
    monkeypatch.setattr(
        backups, "_iter_filtered_dump_lines", lambda p: [b"SELECT 1;\n"]
    )
    dump = tmp_path / "backup.sql.gz"
    dump.write_bytes(b"\x1f\x8b")
    return dump


def _run_restore(fake, dump):
    with patch.object(backups, "_spawn_psql", return_value=fake):
        backups._restore_dump(dump, dry_run=False)


# ---------------------------------------------------------------------------
# The happy path, and the one that must not touch anything
# ---------------------------------------------------------------------------


def test_a_clean_run_streams_the_dump_and_returns(psql_env):
    fake = FakePsql(returncode=0)
    _run_restore(fake, psql_env)
    assert fake.stdin.written == [b"SELECT 1;\n"]
    assert fake.stdin.closed is True
    assert fake.stderr.closed is True


def test_a_dry_run_never_starts_psql(psql_env):
    def explode(*a, **k):
        raise AssertionError("psql was started during a dry run")

    with patch.object(backups, "_spawn_psql", explode):
        backups._restore_dump(psql_env, dry_run=True)


# ---------------------------------------------------------------------------
# Failures. A restore that did not work must never look like one that did.
# ---------------------------------------------------------------------------


def test_a_nonzero_exit_is_raised_with_psql_s_own_first_line(psql_env):
    fake = FakePsql(returncode=3, stderr=b'ERROR:  relation "x" does not exist\nmore\n')
    with pytest.raises(RuntimeError) as e:
        _run_restore(fake, psql_env)
    assert "psql exited 3" in str(e.value)
    assert 'relation "x" does not exist' in str(e.value)


def test_a_broken_pipe_defers_to_psql_s_reason_rather_than_its_own(psql_env):
    """The IO error is the symptom; ON_ERROR_STOP tripping is the cause."""
    fake = FakePsql(
        returncode=1, stderr=b"ERROR:  syntax error\n", write_raises=BrokenPipeError()
    )
    with pytest.raises(RuntimeError) as e:
        _run_restore(fake, psql_env)
    assert "syntax error" in str(e.value)
    assert "BrokenPipeError" not in str(e.value)


def test_a_write_failure_is_still_reported_when_psql_claims_success(psql_env):
    """Exit 0 after a mid-stream write failure means a partial dump."""
    fake = FakePsql(returncode=0, write_raises=OSError("disk went away"))
    with pytest.raises(RuntimeError) as e:
        _run_restore(fake, psql_env)
    assert "psql exited 0" in str(e.value)
    assert "disk went away" in str(e.value)


def test_stdin_is_closed_even_when_writing_failed(psql_env):
    fake = FakePsql(returncode=0, write_raises=OSError("nope"))
    with pytest.raises(RuntimeError):
        _run_restore(fake, psql_env)
    assert fake.stdin.closed is True


def test_a_psql_that_will_not_finish_is_killed(psql_env):
    fake = FakePsql(returncode=0, hangs=True)
    _run_restore(fake, psql_env)
    assert fake.killed is True
    assert fake.waits[0] == 300  # the long wait first, then the short one


def test_unreadable_stderr_does_not_mask_the_exit_code(psql_env):
    fake = FakePsql(returncode=2)
    fake.stderr = FakeStream(raises=ValueError("closed"))
    with pytest.raises(RuntimeError, match="psql exited 2"):
        _run_restore(fake, psql_env)
