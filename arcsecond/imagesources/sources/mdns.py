"""
Resolving a ``.local`` name when the machine's own resolver will not.

A ``.local`` name is not in any DNS server: the machine that owns it answers
for itself, over multicast, on 224.0.0.251:5353 (RFC 6762). Most operating
systems do that for every application — macOS through mDNSResponder, Linux
through Avahi, Windows through its DNS client — but not all of them do, and
not on every network profile. When they do not, ``getaddrinfo`` sends the
query to the configured DNS server instead, which knows nothing about
``.local`` and answers SERVFAIL. That is what a proxy sees as::

    Cannot connect to host skykot.local:80 [DNS server returned general failure]

while the browser two windows away, which speaks mDNS itself, shows the very
same camera. So the proxy speaks it too, as a fallback and only for ``.local``
names — anything else belongs to the machine's resolver and stays there.

This is deliberately a *one-shot* query, not a discovery service: one question
about one name, the first answer wins, and nothing is kept running. mDNS on
the wire is ordinary DNS, so what follows is a small DNS encoder and decoder
rather than anything exotic.
"""

import logging
import socket
import struct
import time

logger = logging.getLogger(__name__)

MDNS_ADDRESS = "224.0.0.251"
MDNS_PORT = 5353
SUFFIX = ".local"

# Long enough for a machine on the same network to answer, short enough that a
# camera which is simply switched off does not hold anything up. A responder
# on the same LAN answers in milliseconds.
DEFAULT_TIMEOUT = 1.5

_TYPE_A = 1
_CLASS_IN = 1
# RFC 6762 §5.4: the top bit of the class field asks the responder to answer
# this one directly to our port rather than multicasting it to the network.
# Without it the answer goes to port 5353, where the system responder — if
# there is one — is listening instead of us.
_UNICAST_RESPONSE = 0x8000
_HEADER = struct.Struct("!6H")
_POINTER_MASK = 0xC0


def is_mdns_name(host: str) -> bool:
    """Whether ``host`` is a name only multicast DNS can answer for."""
    host = (host or "").strip().rstrip(".").lower()
    return host.endswith(SUFFIX) and host != SUFFIX


def _encode_name(name: str) -> bytes:
    parts = [p for p in name.strip().rstrip(".").split(".") if p]
    encoded = b""
    for part in parts:
        raw = part.encode("utf-8")
        if len(raw) > 63:
            raise ValueError(f"label too long in {name!r}")
        encoded += bytes([len(raw)]) + raw
    return encoded + b"\x00"


def _build_query(name: str) -> bytes:
    # Transaction id 0: a responder echoes it back, and having only one query
    # in flight per socket means there is nothing to match it against.
    header = _HEADER.pack(0, 0, 1, 0, 0, 0)
    question = _encode_name(name)
    question += struct.pack("!HH", _TYPE_A, _CLASS_IN | _UNICAST_RESPONSE)
    return header + question


def _read_name(data: bytes, offset: int) -> tuple:
    """``(name, offset_after)``, following compression pointers.

    Answers routinely point back into the question rather than repeating the
    name, so a decoder that cannot follow a pointer reads garbage.
    """
    labels = []
    jumped = False
    end = offset
    seen = 0

    while True:
        if offset >= len(data):
            raise ValueError("truncated name")
        length = data[offset]
        if length == 0:
            offset += 1
            if not jumped:
                end = offset
            break
        if length & _POINTER_MASK == _POINTER_MASK:
            if offset + 1 >= len(data):
                raise ValueError("truncated pointer")
            target = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                end = offset + 2
                jumped = True
            # A pointer chain must make progress towards the start of the
            # packet; anything else is a loop, and a packet from the network
            # is not to be trusted to avoid one.
            if target >= offset:
                raise ValueError("pointer does not move backwards")
            offset = target
            seen += 1
            if seen > 32:
                raise ValueError("too many pointers")
            continue
        offset += 1
        labels.append(data[offset : offset + length].decode("utf-8", "replace"))
        offset += length

    return ".".join(labels), end


def _parse_response(data: bytes, wanted: str) -> list:
    """Every IPv4 address ``wanted`` resolves to in ``data``.

    Only A records for the name that was asked about count. A response may
    carry records about other names entirely — a responder is free to include
    whatever it thinks useful — and answering with one of those would send the
    proxy to a different machine.

    All of them, not the first: a machine with more than one interface answers
    with an address per interface, and which of those the caller can actually
    reach is not something this can tell from here. A Mac answering for itself
    while a virtual network is up is the ordinary case, not an exotic one.
    """
    found: list = []
    try:
        _, _, questions, answers, authority, additional = _HEADER.unpack_from(data)
    except struct.error:
        return found

    offset = _HEADER.size
    try:
        for _ in range(questions):
            _, offset = _read_name(data, offset)
            offset += 4  # QTYPE, QCLASS

        target = wanted.rstrip(".").lower()
        for _ in range(answers + authority + additional):
            name, offset = _read_name(data, offset)
            rtype, rclass, _, length = struct.unpack_from("!HHIH", data, offset)
            offset += 10
            rdata = data[offset : offset + length]
            offset += length
            if (
                rtype == _TYPE_A
                and (rclass & 0x7FFF) == _CLASS_IN
                and len(rdata) == 4
                and name.rstrip(".").lower() == target
            ):
                address = socket.inet_ntoa(rdata)
                if address not in found:
                    found.append(address)
    except (ValueError, struct.error, IndexError):
        # A malformed packet is one more reason to fall back to failing, not a
        # reason to take the proxy down. Anyone on the network can send one.
        # Whatever was read before the damage is still good.
        logger.debug("Ignoring the rest of a malformed mDNS response for %s", wanted)

    return found


def resolve(host: str, timeout: float = DEFAULT_TIMEOUT) -> list:
    """Ask the network for ``host``'s IPv4 addresses. Empty if none answer.

    In the order the responder gave them, which is the order to try them in:
    the caller connects to each until one works, since a machine with several
    interfaces answers for all of them and only some may be reachable.

    Blocking, and short. Call it from a thread when the caller is async.
    """
    if not is_mdns_name(host):
        return []

    name = host.strip().rstrip(".")
    try:
        query = _build_query(name)
    except ValueError:
        return []

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.settimeout(timeout)
        sock.bind(("", 0))
        sock.sendto(query, (MDNS_ADDRESS, MDNS_PORT))

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(0.05, deadline - time.monotonic()))
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                return []
            addresses = _parse_response(data, name)
            if addresses:
                logger.info("Resolved %s to %s over mDNS.", name, addresses)
                return addresses
            # Something else on the network answered, or answered about
            # another name. Keep listening until the deadline rather than
            # taking the first packet as the last word.
    except OSError as e:
        # No multicast route, a firewall in the way, a network that is down:
        # all of them mean "not resolved here", which is what the caller does
        # something about.
        logger.debug("mDNS query for %s failed: %s", name, e)
    finally:
        if sock is not None:
            sock.close()

    return []
