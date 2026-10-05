"""The outbound half of `arcsecond doctor`: every destination the network
manifest declares, probed from this machine.

One finding per manifest entry, carrying the entry's identifier, so that a
line of the report and a line of the network sheet are the same line. A
failure comes with the sentence to send to whoever runs the firewall.

The probes leave from this machine, not from inside the containers. They
share its network path: the containers' connections are translated to this
machine's address on their way out.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

from ..doctor import FAIL, OK, SKIP, WARN, Finding
from . import Destination, Manifest
from . import probe as probing

# Whose connections this machine can stand in for. A browser's leave from the
# user's own workstation, which may sit on another network altogether.
PROBED_FROM_HERE = ("stack", "docker", "tool")

CLOCK_REFERENCE = "licensing"
CLOCK_WARN_SECONDS = 60
CLOCK_FAIL_SECONDS = 300
CERTIFICATE_WARN_DAYS = 14

Prober = Callable[..., probing.Probe]

_WHY = {
    probing.RESOLVE: "the name does not resolve on this machine",
    probing.REFUSED: "the connection was refused",
    probing.TIMED_OUT: "no answer — a firewall on the way, or the far end not answering",
    probing.PROXY: "the proxy would not open the connection",
    probing.CERTIFICATE: "reached, but the certificate presented is not one this machine trusts",
    probing.HANDSHAKE: "reached, but the encrypted handshake failed",
}


def _request(entry: Destination, names: List[str]) -> str:
    """The sentence for the administrator's ticket."""
    where = ", ".join(names)
    return (
        f"Please allow outbound connections from this machine to {where} "
        f"on port {entry.port} ({entry.transport.upper()}). Used for: {entry.purpose}"
    )


def _label(entry: Destination) -> str:
    more = f" (+{len(entry.names) - 1})" if len(entry.names) > 1 else ""
    return f"{entry.names[0]}{more} :{entry.port}"


def _finding(entry: Destination, results: List[probing.Probe]) -> Finding:
    failed = [r for r in results if not r.ok]
    data = {
        "manifest": entry.id,
        "reachable": not failed,
        "need": entry.need,
        "enabled_by": entry.enabled_by,
        "without_it": entry.without_it,
        "probes": [
            {
                "name": r.name,
                "port": r.port,
                "ok": r.ok,
                "failure": r.failure,
                "milliseconds": r.milliseconds,
                "via_proxy": r.via_proxy,
                "certificate_days_left": r.certificate_days_left,
                "certificate_issuer": r.certificate_issuer,
            }
            for r in results
        ],
    }
    if not failed:
        slowest = max((r.milliseconds or 0) for r in results)
        days = [
            r.certificate_days_left
            for r in results
            if r.certificate_days_left is not None
        ]
        detail = f"reachable, {slowest} ms"
        if results[0].via_proxy:
            detail += f", through the proxy {results[0].via_proxy}"
        if days and min(days) < CERTIFICATE_WARN_DAYS:
            return Finding(
                f"net.{entry.id}",
                _label(entry),
                WARN,
                f"{detail}; its certificate expires in {min(days)} day(s)",
                data={
                    **data,
                    "note": "Nothing to do on this side: the far end must renew it.",
                },
            )
        return Finding(f"net.{entry.id}", _label(entry), OK, detail, data=data)

    first = failed[0]
    detail = _WHY.get(first.failure, first.failure or "unreachable")
    if first.failure == probing.CERTIFICATE and first.certificate_issuer:
        detail += f" (signed by {first.certificate_issuer})"
    if len(failed) < len(results):
        detail = f"{len(failed)} of {len(results)} names: " + detail
    if first.failure == probing.CERTIFICATE:
        fix = (
            "If your network inspects encrypted traffic, exempt this destination, or give "
            "your inspection authority's certificate to this machine and to Docker."
        )
    elif first.failure == probing.RESOLVE:
        fix = f"Check this machine's name resolution for {first.name}."
    else:
        fix = _request(entry, [r.name for r in failed])
    status = FAIL if entry.need == "required" and entry.always_on else WARN
    if entry.origin == "docker":
        # Needed to install and to update, never to run.
        status = WARN
    note = f"Without it: {entry.without_it}"
    if not entry.always_on:
        note = f"Only matters with: {entry.enabled_by}. " + note
    return Finding(
        f"net.{entry.id}",
        _label(entry),
        status,
        detail,
        fix=fix,
        data={**data, "note": note},
    )


def check_destinations(
    manifest: Manifest,
    prober: Optional[Prober] = None,
    proxy_for: Optional[Callable[[str], Optional[str]]] = None,
) -> List[Finding]:
    prober = prober or probing.probe
    proxy_for = proxy_for or probing.proxy_for
    entries = [
        d
        for d in manifest.destinations
        if d.origin in PROBED_FROM_HERE
        and d.direction == "outbound"
        and d.names
        and d.test != "none"
    ]

    def run(entry: Destination, name: str) -> probing.Probe:
        return prober(
            name,
            entry.port,
            encrypted=entry.encrypted and entry.test == "handshake",
            want_time=entry.id == CLOCK_REFERENCE,
            proxy=proxy_for(name),
        )

    jobs = [(entry, name) for entry in entries for name in entry.names]
    with ThreadPoolExecutor(max_workers=16) as pool:
        probes = list(pool.map(lambda job: run(*job), jobs))
    by_entry: Dict[str, List[probing.Probe]] = {}
    for (entry, _), result in zip(jobs, probes):
        by_entry.setdefault(entry.id, []).append(result)

    findings = [_finding(entry, by_entry[entry.id]) for entry in entries]
    reference = next((r for r in by_entry.get(CLOCK_REFERENCE, []) if r.ok), None)
    findings.append(check_clock(reference))
    findings.append(_proxy_note(sorted({r.via_proxy for r in probes if r.via_proxy})))
    findings.append(_browser_note(manifest))
    return findings


def check_clock(reference: Optional[probing.Probe]) -> Finding:
    """A wrong clock breaks every certificate check, and looks like anything
    but a clock: it is the first thing to rule out."""
    offset = reference.clock_offset_seconds if reference else None
    if offset is None:
        return Finding(
            "net.clock",
            "This machine's clock",
            SKIP,
            "no reference could be reached to compare it with",
        )
    ahead = "ahead" if offset > 0 else "behind"
    size = abs(offset)
    if size < CLOCK_WARN_SECONDS:
        return Finding(
            "net.clock",
            "This machine's clock",
            OK,
            "within a minute of the reference",
            data={"offset_seconds": round(offset)},
        )
    human = (
        f"{size / 60:.0f} minute(s)" if size < 7200 else f"{size / 3600:.0f} hour(s)"
    )
    return Finding(
        "net.clock",
        "This machine's clock",
        FAIL if size >= CLOCK_FAIL_SECONDS else WARN,
        f"{human} {ahead} of the reference",
        fix="Turn on automatic time setting on this machine. "
        "A wrong clock makes valid certificates look expired or not yet valid.",
        data={"offset_seconds": round(offset)},
    )


def _proxy_note(proxies: List[str]) -> Finding:
    if not proxies:
        return Finding(
            "net.proxy",
            "Proxy",
            OK,
            "none set on this machine: connections leave directly",
        )
    return Finding(
        "net.proxy",
        "Proxy",
        OK,
        f"this machine sends its web traffic through {', '.join(proxies)}",
        data={
            "proxies": proxies,
            "note": "The installation uses it only if the same setting is in its .env file. "
            "The alert feed (port 9092) cannot go through a web proxy.",
        },
    )


def _browser_note(manifest: Manifest) -> Finding:
    names = sorted({n for d in manifest.of("browser") for n in d.names})
    return Finding(
        "net.browser",
        "From the users' browsers",
        SKIP,
        f"{len(names)} destinations are reached by the browsers, not by this machine: not tested here",
        data={"names": names},
    )


def unavailable(findings: List[Finding]) -> List[str]:
    """What an installation loses with the destinations that failed."""
    return [
        f.data["without_it"]
        for f in findings
        if f.key.startswith("net.")
        and f.data.get("reachable") is False
        and f.data.get("without_it")
    ]
