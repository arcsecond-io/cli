from datetime import datetime, timedelta, timezone

from arcsecond.hosting import doctor as check
from arcsecond.hosting import network
from arcsecond.hosting.network import outbound
from arcsecond.hosting.network import probe as probing

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


def _prober(failing=None, clock_ahead=0, certificate_days=200, via=None):
    """A stand-in for the network: every name answers, except those in
    ``failing`` (name -> failure)."""
    failing = failing or {}
    calls = []

    def prober(name, port, encrypted=True, want_time=False, proxy=None, **_):
        calls.append((name, port, encrypted, want_time, proxy))
        if name in failing:
            return probing.Probe(
                name,
                port,
                failure=failing[name],
                certificate_issuer="Observatory Inspection Authority",
            )
        result = probing.Probe(name, port, ok=True, milliseconds=20, via_proxy=via)
        result.certificate_expires = datetime.now(timezone.utc) + timedelta(
            days=certificate_days, hours=1
        )
        if want_time:
            result.server_time = NOW
            result.local_time = NOW + timedelta(seconds=clock_ahead)
        return result

    prober.calls = calls
    return prober


def _run(**kwargs):
    prober = _prober(**kwargs)
    findings = outbound.check_destinations(
        network.load(), prober=prober, proxy_for=lambda name: kwargs.get("via")
    )
    return {f.key: f for f in findings}, prober


def test_every_destination_this_machine_can_stand_in_for_is_probed_and_no_other():
    findings, prober = _run()
    manifest = network.load()
    probed = {name for name, *_ in prober.calls}
    expected = {
        n
        for d in manifest.destinations
        if d.origin in ("stack", "docker", "tool")
        and d.direction == "outbound"
        and d.test != "none"
        for n in d.names
    }
    assert probed == expected
    # The browsers' destinations are not this machine's to answer for.
    assert "server.arcgisonline.com" not in probed
    assert findings["net.browser"].status == check.SKIP
    assert all(
        f.status == check.OK
        for key, f in findings.items()
        if key not in ("net.browser",)
    )


def test_each_finding_carries_its_manifest_entry():
    findings, _ = _run()
    assert findings["net.licensing"].data["manifest"] == "licensing"
    assert findings["net.alerts-feed"].label == "kafka.gcn.nasa.gov (+3) :9092"


def test_the_one_required_destination_failing_is_a_failure_with_the_sentence_to_send():
    findings, _ = _run(failing={"licensing.arcsecond.io": probing.TIMED_OUT})
    f = findings["net.licensing"]
    assert f.status == check.FAIL
    assert f.fix.startswith(
        "Please allow outbound connections from this machine to licensing.arcsecond.io on port 443 (TCP)."
    )
    assert "cannot be activated" in f.data["note"]


def test_an_optional_destination_failing_is_a_warning_that_says_when_it_matters():
    findings, _ = _run(failing={"kafka2.gcn.nasa.gov": probing.TIMED_OUT})
    f = findings["net.alerts-feed"]
    assert f.status == check.WARN
    assert f.detail.startswith("1 of 4 names:")
    assert "kafka2.gcn.nasa.gov on port 9092" in f.fix
    assert f.data["note"].startswith("Only matters with: the transient-alerts service")


def test_what_is_only_needed_to_install_never_fails_a_running_installation():
    findings, _ = _run(failing={"ghcr.io": probing.TIMED_OUT})
    assert findings["net.software-images"].status == check.WARN


def test_an_untrusted_certificate_is_not_reported_as_a_blocked_port():
    findings, _ = _run(failing={"simbad.cds.unistra.fr": probing.CERTIFICATE})
    f = findings["net.catalogue-objects"]
    assert "not one this machine trusts" in f.detail
    assert "signed by Observatory Inspection Authority" in f.detail
    assert "inspects encrypted traffic" in f.fix and "Please allow" not in f.fix


def test_a_name_that_does_not_resolve_is_a_name_problem():
    findings, _ = _run(failing={"celestrak.org": probing.RESOLVE})
    assert "name resolution" in findings["net.catalogue-satellites"].fix


def test_a_proxy_in_use_is_said():
    findings, prober = _run(via="proxy.observatory.example:3128")
    assert (
        "through the proxy proxy.observatory.example:3128"
        in findings["net.licensing"].detail
    )
    assert all(call[4] == "proxy.observatory.example:3128" for call in prober.calls)


def test_a_certificate_about_to_expire_is_worth_a_word_and_nothing_to_do():
    findings, _ = _run(certificate_days=5)
    f = findings["net.licensing"]
    assert f.status == check.WARN and "expires in 5 day(s)" in f.detail
    # Still reachable: nothing is lost, and the exit code says so.
    assert outbound.unavailable(list(findings.values())) == []
    assert check.exit_code(list(findings.values())) == 0


def test_the_proxy_line_says_which_or_none():
    assert "none set" in _run()[0]["net.proxy"].detail
    through = _run(via="proxy.observatory.example:3128")[0]["net.proxy"]
    assert (
        "proxy.observatory.example:3128" in through.detail
        and "9092" in through.data["note"]
    )


def test_the_clock_is_compared_with_the_reference():
    assert _run(clock_ahead=5)[0]["net.clock"].status == check.OK
    slow = _run(clock_ahead=-120)[0]["net.clock"]
    assert slow.status == check.WARN and "2 minute(s) behind" in slow.detail
    wrong = _run(clock_ahead=3 * 3600)[0]["net.clock"]
    assert wrong.status == check.FAIL and "3 hour(s) ahead" in wrong.detail
    assert "certificates" in wrong.fix


def test_with_no_reference_the_clock_is_not_judged():
    findings, _ = _run(failing={"licensing.arcsecond.io": probing.TIMED_OUT})
    assert findings["net.clock"].status == check.SKIP


def test_only_the_reference_is_asked_the_time():
    _, prober = _run()
    assert [name for name, _, _, want_time, _ in prober.calls if want_time] == [
        "licensing.arcsecond.io"
    ]
