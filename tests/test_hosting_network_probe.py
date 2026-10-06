"""The probe against a deliberately broken network, built from local sockets:
a port nothing listens on, a server whose certificate no authority signed (what
an inspecting proxy looks like from inside), a proxy that says no, and a
reference whose clock is not ours."""

import shutil
import socket
import ssl
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from arcsecond.hosting.network import probe as probing


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(handler, wrap=None):
    """A one-thread server on a local port; ``handler`` gets each connection."""
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    listener.settimeout(5)

    def loop():
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            try:
                if wrap is not None:
                    conn = wrap(conn)
                handler(conn)
            except (OSError, ssl.SSLError):
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    threading.Thread(target=loop, daemon=True).start()
    return listener, listener.getsockname()[1]


@pytest.fixture(scope="module")
def self_signed(tmp_path_factory):
    if shutil.which("openssl") is None:
        pytest.skip("openssl is not installed")
    folder = tmp_path_factory.mktemp("authority")
    key, cert = folder / "key.pem", folder / "cert.pem"
    made = subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "30",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/O=Observatory Inspection Authority/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
        ],
        capture_output=True,
    )
    if made.returncode != 0:
        pytest.skip("this openssl cannot make the test certificate")
    return key, cert


def test_a_port_nothing_listens_on_is_refused_not_timed_out():
    # The probe's own timeout, not a shorter one: Windows retries a refused
    # connection for about two seconds per address before saying so.
    result = probing.probe("localhost", _free_port(), timeout=probing.TIMEOUT)
    assert not result.ok and result.failure == probing.REFUSED


def test_a_name_that_does_not_exist_fails_at_the_name():
    result = probing.probe("no-such-host.invalid", 443, timeout=2)
    assert result.failure == probing.RESOLVE


def test_a_plain_connection_is_enough_when_no_encryption_is_expected():
    listener, port = _serve(lambda conn: None)
    try:
        result = probing.probe("localhost", port, encrypted=False, timeout=2)
        assert result.ok and result.milliseconds is not None and result.addresses
    finally:
        listener.close()


def test_an_inspecting_proxy_is_recognised_by_its_certificate(self_signed):
    key, cert = self_signed
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    listener, port = _serve(
        lambda conn: conn.recv(1),
        wrap=lambda c: context.wrap_socket(c, server_side=True),
    )
    try:
        result = probing.probe("localhost", port, timeout=3)
    finally:
        listener.close()
    assert not result.ok and result.failure == probing.CERTIFICATE
    assert result.certificate_issuer == "Observatory Inspection Authority"


def test_a_trusted_certificate_gives_its_expiry_and_the_far_ends_clock(
    self_signed, monkeypatch
):
    key, cert = self_signed
    theirs = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=3)

    def answer(conn):
        conn.recv(4096)
        conn.sendall(
            f"HTTP/1.1 200 OK\r\nDate: {format_datetime(theirs, usegmt=True)}\r\n\r\n".encode()
        )

    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert, key)
    listener, port = _serve(
        answer, wrap=lambda c: server.wrap_socket(c, server_side=True)
    )
    # This machine trusts that authority, for the length of the test.
    trusting = ssl.create_default_context(cafile=str(cert))
    monkeypatch.setattr(probing.ssl, "create_default_context", lambda *a, **k: trusting)
    try:
        result = probing.probe("localhost", port, want_time=True, timeout=3)
    finally:
        listener.close()
    assert result.ok, result.detail
    assert 28 <= result.certificate_days_left <= 30
    # Our clock reads three hours ahead of theirs: the wrong-clock case.
    assert abs(result.clock_offset_seconds - 3 * 3600) < 30


def test_a_proxy_that_refuses_is_named_as_the_proxy():
    def refuse(conn):
        conn.recv(4096)
        conn.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")

    listener, port = _serve(refuse)
    try:
        result = probing.probe(
            "licensing.arcsecond.io",
            443,
            proxy=f"http://user:secret@127.0.0.1:{port}",
            timeout=3,
        )
    finally:
        listener.close()
    assert result.failure == probing.PROXY and "403" in result.detail
    assert result.via_proxy == f"127.0.0.1:{port}"  # never the account


def test_a_proxy_that_accepts_carries_the_connection_through():
    seen = []

    def accept(conn):
        seen.append(conn.recv(4096).decode())
        conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")

    listener, port = _serve(accept)
    try:
        result = probing.probe(
            "example.invalid",
            8443,
            encrypted=False,
            proxy=f"127.0.0.1:{port}",
            timeout=3,
        )
    finally:
        listener.close()
    assert result.ok
    assert seen[0].startswith("CONNECT example.invalid:8443 HTTP/1.1")


def test_a_proxy_address_is_shown_without_its_account():
    assert (
        probing.redact_proxy("http://user:secret@proxy.example:3128")
        == "proxy.example:3128"
    )
    assert probing.redact_proxy("proxy.example:8080") == "proxy.example:8080"
