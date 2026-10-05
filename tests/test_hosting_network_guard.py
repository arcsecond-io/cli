"""The lines below are real `tcpdump -nn` output from the audit of 2026-10-05,
trimmed: the guard reads the tool's text, so the tests feed it the tool's text."""

from arcsecond.hosting.network import guard

SUBNET = "172.21.0.0/16"

LOOKUP_SIMBAD = [
    "12:24:37.043364 ?     Out IP 192.168.65.6.55805 > 192.168.65.7.53: 32028+ A? simbad.cds.unistra.fr. (39)",
    "12:24:37.142728 ?     In  IP 192.168.65.7.53 > 192.168.65.6.55805: 32028 1/0/0 A 130.79.128.4 (76)",
]
OPEN_SIMBAD = (
    "12:24:37.149820 ?     P   IP 172.21.0.12.33040 > 130.79.128.4.443: Flags [S], seq 490477156, win 64240, length 0"
)
LOOKUP_STATICS = [
    "12:19:31.212715 ?     Out IP 192.168.65.6.63966 > 192.168.65.7.53: 6503+ A? statics.arcsecond.io. (38)",
    "12:19:31.312715 ?     In  IP 192.168.65.7.53 > 192.168.65.6.63966: 6503 5/0/0 CNAME d2336t190ivzhv.cloudfront.net., "
    "A 3.165.190.70, A 3.165.190.24 (281)",
]
LOOKUP_GITHUB = [
    "12:12:01.100000 ?     Out IP 192.168.65.6.40000 > 192.168.65.7.53: 777+ A? api.github.com. (32)",
    "12:12:01.200000 ?     In  IP 192.168.65.7.53 > 192.168.65.6.40000: 777 1/0/0 A 140.82.121.5 (48)",
]


def _syn(source, address, port):
    return f"12:30:00.000000 ?     P   IP {source}.40000 > {address}.{port}: Flags [S], seq 1, win 64240, length 0"


def test_a_declared_destination_passes_under_its_manifest_entry():
    verdict = guard.check(LOOKUP_SIMBAD + [OPEN_SIMBAD], SUBNET)
    assert verdict.ok
    assert [ident for ident, _ in verdict.declared] == ["catalogue-objects"]


def test_a_name_behind_an_alias_is_named_by_what_was_asked_for():
    """statics.arcsecond.io answers through a content network's alias; the
    connection is to what the stack asked for, not to the alias."""
    verdict = guard.check(LOOKUP_STATICS + [_syn("172.21.0.7", "3.165.190.24", 443)], SUBNET)
    assert verdict.ok
    assert verdict.declared[0][0] == "sky-brightness"


def test_an_undeclared_destination_fails_and_is_named():
    verdict = guard.check(LOOKUP_GITHUB + [_syn("172.21.0.7", "140.82.121.5", 443)], SUBNET)
    assert not verdict.ok
    assert verdict.undeclared[0].names == ("api.github.com",)
    assert "api.github.com" in guard.report(verdict)
    assert "manifest.toml" in guard.report(verdict)


def test_the_right_name_on_an_undeclared_port_fails():
    verdict = guard.check(LOOKUP_SIMBAD + [_syn("172.21.0.12", "130.79.128.4", 80)], SUBNET)
    assert not verdict.ok


def test_a_bare_address_nobody_looked_up_fails():
    verdict = guard.check([_syn("172.21.0.7", "203.0.113.9", 443)], SUBNET)
    assert not verdict.ok
    assert "no name was looked up" in guard.report(verdict)


def test_a_declared_browser_destination_is_not_the_stacks_to_use():
    lines = [
        "12:00:00.000000 ?     Out IP 192.168.65.6.41000 > 192.168.65.7.53: 9+ A? server.arcgisonline.com. (40)",
        "12:00:00.100000 ?     In  IP 192.168.65.7.53 > 192.168.65.6.41000: 9 1/0/0 A 198.51.100.7 (56)",
        _syn("172.21.0.7", "198.51.100.7", 443),
    ]
    assert not guard.check(lines, SUBNET).ok


def test_instruments_on_the_site_are_local_and_containers_talking_to_each_other_are_nothing():
    lines = [
        _syn("172.21.0.12", "192.168.65.254", 32423),  # the simulator, through the host gateway
        _syn("172.21.0.7", "172.21.0.6", 5432),  # backend to database
    ]
    verdict = guard.check(lines, SUBNET)
    assert verdict.ok
    assert [(c.address, c.port) for c in verdict.local] == [("192.168.65.254", 32423)]


def test_other_stacks_and_ignored_containers_are_not_ours_to_answer_for():
    lines = LOOKUP_GITHUB + [
        _syn("172.20.0.5", "140.82.121.5", 443),  # another compose project on the same machine
        _syn("172.21.0.2", "140.82.121.5", 443),  # the instrument simulator, checking for its own updates
    ]
    assert guard.check(lines, SUBNET, ignore_sources=["172.21.0.2"]).ok
    assert not guard.check(lines, SUBNET).ok


def test_the_command_exits_non_zero_on_an_undeclared_destination(tmp_path, capsys):
    capture = tmp_path / "capture.txt"
    capture.write_text("\n".join(LOOKUP_GITHUB + [_syn("172.21.0.7", "140.82.121.5", 443)]))
    assert guard.main([str(capture), "--subnet", SUBNET]) == 1
    assert "NOT DECLARED" in capsys.readouterr().out
    capture.write_text("\n".join(LOOKUP_SIMBAD + [OPEN_SIMBAD]))
    assert guard.main([str(capture), "--subnet", SUBNET]) == 0
