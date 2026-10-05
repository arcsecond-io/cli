"""Reachability probes: can this machine reach a destination, and how.

One probe is what an administrator would do by hand to answer "is it the
firewall": resolve the name, open the connection, complete the encrypted
handshake, read the certificate. It sends nothing about the observatory —
no account, no key, no identifier — and asks the far end for nothing but
its certificate, and, from one reference host, the time.

Each step that fails is named for what it is, because the remedies differ:
a name that does not resolve is not a blocked port, and a certificate this
machine does not trust is neither — it is usually an inspecting proxy.
"""

import base64
import socket
import ssl
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional
from urllib.parse import urlsplit

TIMEOUT = 6.0

# What went wrong, when something did.
RESOLVE = "resolve"  # the name has no address here
REFUSED = "refused"  # something answered "no" at once
TIMED_OUT = "timeout"  # nothing answered: the usual face of a firewall
PROXY = "proxy"  # the proxy would not open the way
CERTIFICATE = "certificate"  # reached, but not with a certificate this machine trusts
HANDSHAKE = "handshake"  # reached, and the encrypted handshake failed otherwise


@dataclass
class Probe:
    name: str
    port: int
    ok: bool = False
    failure: Optional[str] = None
    detail: str = ""
    addresses: List[str] = field(default_factory=list)
    milliseconds: Optional[int] = None
    via_proxy: Optional[str] = None
    certificate_expires: Optional[datetime] = None
    certificate_issuer: str = ""
    server_time: Optional[datetime] = None
    local_time: Optional[datetime] = None

    @property
    def certificate_days_left(self) -> Optional[int]:
        if self.certificate_expires is None:
            return None
        return (self.certificate_expires - datetime.now(timezone.utc)).days

    @property
    def clock_offset_seconds(self) -> Optional[float]:
        """This machine's clock minus the far end's. Positive: this one is ahead."""
        if self.server_time is None or self.local_time is None:
            return None
        return (self.local_time - self.server_time).total_seconds()


def proxy_for(name: str) -> Optional[str]:
    """The proxy this machine's environment designates for HTTPS to ``name``,
    or None. The same variables the installation's own libraries read."""
    try:
        if urllib.request.proxy_bypass(name):
            return None
    except Exception:  # noqa: BLE001 — a malformed NO_PROXY is not this probe's failure
        pass
    proxies = urllib.request.getproxies()
    return proxies.get("https") or proxies.get("all") or None


def redact_proxy(url: str) -> str:
    """A proxy address without the account it may carry."""
    parts = urlsplit(url if "//" in url else f"//{url}")
    host = parts.hostname or ""
    return f"{host}:{parts.port}" if parts.port else host


def _issuer_of(der: bytes) -> str:
    """The issuer's name out of a certificate this machine did not verify.
    Python only decodes certificates it has verified, except through this one
    helper; when it is not there, the issuer is simply not reported."""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".pem") as handle:
            handle.write(ssl.DER_cert_to_PEM_cert(der))
            handle.flush()
            decoded = ssl._ssl._test_decode_cert(handle.name)  # type: ignore[attr-defined]
        return _name(decoded.get("issuer", ()))
    except Exception:  # noqa: BLE001
        return ""


def _name(rdns) -> str:
    fields = {key: value for rdn in rdns for key, value in rdn}
    return fields.get("organizationName") or fields.get("commonName") or ""


def _open(name: str, port: int, proxy: Optional[str], timeout: float) -> socket.socket:
    """A connection to ``name``:``port``, through ``proxy`` when there is one."""
    if not proxy:
        return socket.create_connection((name, port), timeout=timeout)
    parts = urlsplit(proxy if "//" in proxy else f"//{proxy}")
    sock = socket.create_connection(
        (parts.hostname, parts.port or 3128), timeout=timeout
    )
    request = f"CONNECT {name}:{port} HTTP/1.1\r\nHost: {name}:{port}\r\n"
    if parts.username:
        token = base64.b64encode(
            f"{parts.username}:{parts.password or ''}".encode()
        ).decode()
        request += f"Proxy-Authorization: Basic {token}\r\n"
    sock.sendall((request + "\r\n").encode())
    answer = b""
    while b"\r\n\r\n" not in answer and len(answer) < 8192:
        chunk = sock.recv(4096)
        if not chunk:
            break
        answer += chunk
    status = answer.split(b"\r\n", 1)[0].decode(errors="replace")
    if " 200" not in status:
        sock.close()
        raise ProxyRefused(status or "the proxy closed the connection")
    return sock


class ProxyRefused(OSError):
    pass


def _server_time(tls: ssl.SSLSocket, name: str) -> Optional[datetime]:
    """The far end's clock, from the Date line every web server sends."""
    try:
        tls.sendall(
            f"HEAD / HTTP/1.1\r\nHost: {name}\r\nConnection: close\r\n\r\n".encode()
        )
        answer = b""
        while b"\r\n\r\n" not in answer and len(answer) < 16384:
            chunk = tls.recv(4096)
            if not chunk:
                break
            answer += chunk
        for line in answer.decode(errors="replace").split("\r\n"):
            if line.lower().startswith("date:"):
                return parsedate_to_datetime(line.split(":", 1)[1].strip())
    except (OSError, ValueError, TypeError):
        pass
    return None


def _connect(
    result: Probe, timeout: float, proxy: Optional[str]
) -> Optional[socket.socket]:
    """The open connection, or None with the reason written on ``result``."""
    try:
        return _open(result.name, result.port, proxy, timeout)
    except ProxyRefused as e:
        result.failure, result.detail = PROXY, str(e)
    except (socket.timeout, TimeoutError):
        result.failure = TIMED_OUT
        result.detail = f"no answer within {timeout:.0f} seconds"
    except ConnectionRefusedError as e:
        result.failure, result.detail = REFUSED, str(e)
    except OSError as e:
        result.failure, result.detail = TIMED_OUT, str(e)
    return None


def _handshake(
    result: Probe, sock: socket.socket, want_time: bool, timeout: float, proxy
) -> None:
    """Complete the encrypted handshake on ``sock`` and read the certificate."""
    name = result.name
    try:
        with ssl.create_default_context().wrap_socket(
            sock, server_hostname=name
        ) as tls:
            certificate = tls.getpeercert() or {}
            result.certificate_issuer = _name(certificate.get("issuer", ()))
            if certificate.get("notAfter"):
                result.certificate_expires = datetime.fromtimestamp(
                    ssl.cert_time_to_seconds(certificate["notAfter"]), tz=timezone.utc
                )
            if want_time:
                result.local_time = datetime.now(timezone.utc)
                result.server_time = _server_time(tls, name)
            result.ok = True
    except ssl.SSLCertVerificationError as e:
        result.failure = CERTIFICATE
        result.detail = e.verify_message or str(e)
        result.certificate_issuer = _unverified_issuer(
            name, result.port, proxy, timeout
        )
    except (ssl.SSLError, OSError) as e:
        result.failure, result.detail = HANDSHAKE, str(e)


def probe(
    name: str,
    port: int,
    encrypted: bool = True,
    want_time: bool = False,
    timeout: float = TIMEOUT,
    proxy: Optional[str] = None,
) -> Probe:
    """Resolve, connect, and (when ``encrypted``) complete the handshake."""
    result = Probe(
        name=name, port=port, via_proxy=redact_proxy(proxy) if proxy else None
    )

    if not proxy:
        try:
            infos = socket.getaddrinfo(name, port, type=socket.SOCK_STREAM)
            result.addresses = sorted({info[4][0] for info in infos})
        except socket.gaierror as e:
            result.failure, result.detail = RESOLVE, str(e)
            return result

    started = time.monotonic()
    sock = _connect(result, timeout, proxy)
    if sock is None:
        return result
    result.milliseconds = int((time.monotonic() - started) * 1000)

    if not encrypted:
        sock.close()
        result.ok = True
        return result

    _handshake(result, sock, want_time, timeout, proxy)
    return result


def _unverified_issuer(
    name: str, port: int, proxy: Optional[str], timeout: float
) -> str:
    """Who signed the certificate this machine refused: the name an
    administrator needs to recognise their own inspecting proxy."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with context.wrap_socket(
            _open(name, port, proxy, timeout), server_hostname=name
        ) as tls:
            der = tls.getpeercert(binary_form=True)
        return _issuer_of(der) if der else ""
    except OSError:
        return ""
