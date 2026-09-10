"""Tests for resolving a `.local` name when the machine's resolver will not.

Nothing here touches the network: the wire format is what matters, so the
packets are built by hand and fed to the parser. A responder on the other end
is somebody else's software, and a test that waited for one would pass or fail
according to what happens to be plugged in.
"""

import socket
import struct

import pytest

from arcsecond.imagesources.sources import mdns

NAME = "skykot.local"


def _response(records, questions=(NAME,), flags=0x8400):
    """A response packet carrying ``records`` as ``(name, type, rdata)``."""
    header = mdns._HEADER.pack(0, flags, len(questions), len(records), 0, 0)
    body = b""
    for question in questions:
        body += mdns._encode_name(question) + struct.pack("!HH", 1, 1)
    for name, rtype, rdata in records:
        body += mdns._encode_name(name)
        body += struct.pack("!HHIH", rtype, 1, 120, len(rdata)) + rdata
    return header + body


# ---------------------------------------------------------------------------
# Which names this is for
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "host,expected",
    [
        ("skykot.local", True),
        ("skykot.local.", True),
        ("SKYKOT.LOCAL", True),
        ("allsky.example.com", False),
        ("192.168.1.42", False),
        (".local", False),
        ("", False),
    ],
)
def test_only_local_names_are_asked_of_the_network(host, expected):
    """Everything else belongs to the machine's resolver and stays there."""
    assert mdns.is_mdns_name(host) is expected


def test_a_name_that_is_not_local_is_not_even_asked(monkeypatch):
    def no_sockets(*a, **k):
        raise AssertionError("opened a socket")

    monkeypatch.setattr(mdns.socket, "socket", no_sockets)
    assert mdns.resolve("allsky.example.com") == []


# ---------------------------------------------------------------------------
# The query
# ---------------------------------------------------------------------------


def test_the_query_asks_for_one_a_record_by_name():
    query = mdns._build_query(NAME)
    _, _, questions, answers, _, _ = mdns._HEADER.unpack_from(query)
    assert (questions, answers) == (1, 0)
    assert mdns._encode_name(NAME) in query


def test_the_query_asks_to_be_answered_directly():
    """Without the unicast bit the answer goes to port 5353, where the
    system responder is listening instead of us."""
    query = mdns._build_query(NAME)
    _, qclass = struct.unpack("!HH", query[-4:])
    assert qclass & mdns._UNICAST_RESPONSE
    assert qclass & 0x7FFF == mdns._CLASS_IN


# ---------------------------------------------------------------------------
# The answer
# ---------------------------------------------------------------------------


def test_an_address_is_read_from_the_answer():
    packet = _response([(NAME, 1, socket.inet_aton("192.168.1.42"))])
    assert mdns._parse_response(packet, NAME) == ["192.168.1.42"]


def test_a_name_written_as_a_pointer_is_followed():
    """Responders routinely point back at the question instead of repeating
    the name, so a decoder that cannot follow one reads garbage."""
    header = mdns._HEADER.pack(0, 0x8400, 1, 1, 0, 0)
    question = mdns._encode_name(NAME) + struct.pack("!HH", 1, 1)
    pointer = struct.pack("!H", 0xC000 | mdns._HEADER.size)
    answer = pointer + struct.pack("!HHIH", 1, 1, 120, 4)
    answer += socket.inet_aton("192.168.1.42")

    assert mdns._parse_response(header + question + answer, NAME) == ["192.168.1.42"]


def test_an_answer_about_another_machine_is_not_taken():
    """A responder may say whatever it finds useful. Taking one of those
    would send the proxy to a different machine entirely."""
    packet = _response([("other.local", 1, socket.inet_aton("10.0.0.1"))])
    assert mdns._parse_response(packet, NAME) == []


def test_the_right_answer_is_found_among_others():
    packet = _response(
        [
            ("other.local", 1, socket.inet_aton("10.0.0.1")),
            (NAME, 1, socket.inet_aton("192.168.1.42")),
        ]
    )
    assert mdns._parse_response(packet, NAME) == ["192.168.1.42"]


def test_every_address_a_machine_answers_with_is_kept():
    """A machine with more than one interface answers with one address each,
    and which of them the caller can reach is not knowable from here."""
    packet = _response(
        [
            (NAME, 1, socket.inet_aton("192.168.64.1")),
            (NAME, 1, socket.inet_aton("192.168.1.97")),
        ]
    )
    assert mdns._parse_response(packet, NAME) == ["192.168.64.1", "192.168.1.97"]


def test_the_same_address_twice_is_kept_once():
    packet = _response(
        [
            (NAME, 1, socket.inet_aton("192.168.1.97")),
            (NAME, 1, socket.inet_aton("192.168.1.97")),
        ]
    )
    assert mdns._parse_response(packet, NAME) == ["192.168.1.97"]


def test_a_record_that_is_not_an_address_is_ignored():
    packet = _response([(NAME, 12, mdns._encode_name("something.local"))])
    assert mdns._parse_response(packet, NAME) == []


@pytest.mark.parametrize(
    "packet",
    [
        b"",
        b"\x00\x01\x02",
        mdns._HEADER.pack(0, 0x8400, 1, 1, 0, 0) + b"\x05sky",  # truncated name
        # A pointer to itself: a packet from the network must not be trusted
        # to avoid a loop.
        mdns._HEADER.pack(0, 0x8400, 0, 1, 0, 0) + struct.pack("!H", 0xC00C),
    ],
)
def test_a_malformed_packet_is_ignored_rather_than_fatal(packet):
    """Anyone on the network can send one, and the proxy must survive it."""
    assert mdns._parse_response(packet, NAME) == []


# ---------------------------------------------------------------------------
# The query as a whole
# ---------------------------------------------------------------------------


def test_nothing_answering_is_an_answer(monkeypatch):
    class SilentSocket:
        def setsockopt(self, *a):
            pass

        def settimeout(self, *a):
            pass

        def bind(self, *a):
            pass

        def sendto(self, *a):
            pass

        def recvfrom(self, *a):
            raise socket.timeout()

        def close(self):
            pass

    monkeypatch.setattr(mdns.socket, "socket", lambda *a, **k: SilentSocket())
    assert mdns.resolve(NAME, timeout=0.05) == []


def test_a_network_that_refuses_multicast_is_not_fatal(monkeypatch):
    """No route, or a firewall in the way: that means "not resolved here",
    which is a thing the caller reports rather than a crash."""

    def no_multicast(*a, **k):
        raise OSError("Network is unreachable")

    monkeypatch.setattr(mdns.socket, "socket", no_multicast)
    assert mdns.resolve(NAME, timeout=0.05) == []


# ---------------------------------------------------------------------------
# The resolver the proxy hands to aiohttp
# ---------------------------------------------------------------------------


def _resolve(host, family=socket.AF_INET, default=None):
    """Run the proxy's resolver for ``host``, with ``default`` standing in for
    the machine's own resolver."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    from arcsecond.imagesources.sources.network import _mdns_aware_resolver

    if default is None:
        machine = AsyncMock(side_effect=socket.gaierror(-2, "not known"))
    else:
        machine = AsyncMock(return_value=default)

    async def main():
        resolver = _mdns_aware_resolver()
        with patch.object(
            resolver, "_default", AsyncMock(resolve=machine, close=AsyncMock())
        ):
            try:
                return await resolver.resolve(host, 80, family)
            finally:
                await resolver.close()

    return asyncio.run(main())


def test_the_machine_resolver_is_asked_first():
    """It is the answer almost every time, and mDNS is only for what is left."""
    answer = [{"hostname": "cam.example.com", "host": "10.0.0.5", "port": 80}]
    assert _resolve("cam.example.com", default=answer) == answer


def test_a_local_name_falls_back_to_the_network(monkeypatch):
    monkeypatch.setattr(mdns, "resolve", lambda host, *a, **k: ["192.168.1.42"])

    (result,) = _resolve(NAME)
    assert result["host"] == "192.168.1.42"
    assert result["hostname"] == NAME
    assert result["port"] == 80
    assert result["family"] == socket.AF_INET


def test_every_address_is_offered_to_aiohttp(monkeypatch):
    """aiohttp tries them in turn, which is what makes a multi-homed
    responder work rather than work half the time."""
    monkeypatch.setattr(
        mdns, "resolve", lambda host, *a, **k: ["192.168.64.1", "192.168.1.97"]
    )
    assert [r["host"] for r in _resolve(NAME)] == ["192.168.64.1", "192.168.1.97"]


def test_a_name_nothing_answers_for_still_fails(monkeypatch):
    """The connection error the operator gets must stay the real one."""
    monkeypatch.setattr(mdns, "resolve", lambda host, *a, **k: [])

    with pytest.raises(socket.gaierror):
        _resolve(NAME)


def test_an_ipv6_lookup_is_not_answered_with_an_ipv4_address(monkeypatch):
    """Only A records are asked for, so this is not ours to answer."""
    monkeypatch.setattr(mdns, "resolve", lambda host, *a, **k: ["192.168.1.42"])

    with pytest.raises(socket.gaierror):
        _resolve(NAME, family=socket.AF_INET6)
