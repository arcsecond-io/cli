"""The guard that keeps the network manifest honest.

Given what a running stack was seen doing on the network, say which
connections the manifest does not declare. Continuous integration runs it
against a capture of the stack built from the tree under test, so a new
outbound call cannot ship without its line in `manifest.toml` — and so the
sheet generated from that file cannot lie by omission.

The capture is `tcpdump` text, taken where both the containers' connections
and the machine's name lookups are visible:

    tcpdump -i any -nn 'udp port 53 or (tcp[13] & 2 != 0 and tcp[13] & 16 == 0)'

A connection is attributed to the stack by its source address (the compose
network), and named through the lookups seen in the same capture: Docker
forwards the containers' lookups from the machine itself, so the question and
its answer are paired by the lookup's identifier.

    python -m arcsecond.hosting.network.guard capture.txt --subnet 172.21.0.0/16
"""

import argparse
import ipaddress
import re
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from . import Manifest, load

_QUERY = re.compile(
    r"IP6? (\S+)\.(\d+) > \S+\.53: (\d+)\+?[^ ]* (?:A|AAAA)\? (\S+?)\.? "
)
_ANSWER = re.compile(r"IP6? \S+\.53 > (\S+)\.(\d+): (\d+)[^ ]* \d+/\d+/\d+ (.*)$")
_ADDRESS = re.compile(r"\bA{1,4} ([0-9a-fA-F:.]+)")
_SYN = re.compile(
    r"IP (\d+\.\d+\.\d+\.\d+)\.\d+ > (\d+\.\d+\.\d+\.\d+)\.(\d+): Flags \[S\]"
)


@dataclass(frozen=True)
class Connection:
    source: str
    address: str
    port: int
    names: Tuple[str, ...]


@dataclass(frozen=True)
class Verdict:
    declared: Tuple[Tuple[str, Connection], ...]  # (manifest id, connection)
    local: Tuple[Connection, ...]
    undeclared: Tuple[Connection, ...]

    @property
    def ok(self) -> bool:
        return not self.undeclared


def parse_capture(
    lines: Iterable[str],
) -> Tuple[Dict[str, Set[str]], List[Tuple[str, str, int]]]:
    """(address -> names it was looked up under, [(source, address, port)])."""
    asked: Dict[Tuple[str, str, str], str] = {}
    names: Dict[str, Set[str]] = {}
    opened: List[Tuple[str, str, int]] = []
    for line in lines:
        match = _SYN.search(line)
        if match:
            opened.append((match.group(1), match.group(2), int(match.group(3))))
            continue
        match = _QUERY.search(line)
        if match:
            client, port, ident, name = match.groups()
            asked[(client, port, ident)] = name.lower()
            continue
        match = _ANSWER.search(line)
        if match:
            client, port, ident, answers = match.groups()
            name = asked.get((client, port, ident))
            if name:
                for address in _ADDRESS.findall(answers):
                    names.setdefault(address, set()).add(name)
    return names, opened


# The private ranges a site's own network is made of, spelled out:
# `ip.is_private` also takes in documentation and benchmarking ranges, and a
# guard should not wave through more than it can name.
_ON_SITE = tuple(
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
    )
)


def _stays_on_site(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return any(ip in network for network in _ON_SITE)


def check(
    lines: Iterable[str],
    subnet: str,
    manifest: Optional[Manifest] = None,
    ignore_sources: Iterable[str] = (),
) -> Verdict:
    """Sort every connection opened from ``subnet`` into declared, local and
    undeclared. ``ignore_sources`` are containers that are not Arcsecond.local
    (a simulator, a mock) and whose traffic is not ours to declare."""
    manifest = manifest or load()
    network = ipaddress.ip_network(subnet)
    ignored = set(ignore_sources)
    names, opened = parse_capture(lines)

    declared, local, undeclared = {}, {}, {}
    for source, address, port in opened:
        if source in ignored or ipaddress.ip_address(source) not in network:
            continue
        if ipaddress.ip_address(address) in network:
            continue  # one container to another
        connection = Connection(
            source, address, port, tuple(sorted(names.get(address, ())))
        )
        key = (address, port)
        if _stays_on_site(address):
            local[key] = connection
            continue
        entry = next(
            (
                d
                for name in connection.names
                if (d := manifest.find(name, port, origin="stack"))
            ),
            None,
        )
        if entry is not None:
            declared[key] = (entry.id, connection)
        else:
            undeclared[key] = connection
    return Verdict(
        tuple(declared.values()), tuple(local.values()), tuple(undeclared.values())
    )


def report(verdict: Verdict) -> str:
    out = []
    by_entry: Dict[str, Set[str]] = {}
    for ident, connection in verdict.declared:
        by_entry.setdefault(ident, set()).update(
            f"{n}:{connection.port}" for n in connection.names
        )
    out.append(f"Declared in the manifest ({len(by_entry)} entries):")
    out += [
        f"  {ident:<26} {', '.join(sorted(seen))}"
        for ident, seen in sorted(by_entry.items())
    ]
    if verdict.local:
        out.append(f"On the local network ({len(verdict.local)}):")
        out += [f"  {c.address}:{c.port}" for c in verdict.local]
    if verdict.undeclared:
        out.append(f"NOT DECLARED ({len(verdict.undeclared)}):")
        for c in verdict.undeclared:
            what = ", ".join(c.names) or "no name was looked up for this address"
            out.append(f"  {c.address}:{c.port}  ({what})  from {c.source}")
        out.append("")
        out.append(
            "The stack contacted a destination that arcsecond/hosting/network/manifest.toml "
            "does not list. Either the call should not exist, or it needs its entry there: "
            "the network sheet given to administrators is generated from that file."
        )
    else:
        out.append("Nothing undeclared.")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("capture", help="tcpdump text output, or - for standard input")
    parser.add_argument(
        "--subnet", required=True, help="the compose network, e.g. 172.21.0.0/16"
    )
    parser.add_argument(
        "--ignore-source", action="append", default=[], metavar="ADDRESS"
    )
    args = parser.parse_args(argv)
    handle = (
        sys.stdin
        if args.capture == "-"
        else open(args.capture, encoding="utf-8", errors="replace")
    )
    with handle:
        verdict = check(handle, args.subnet, ignore_sources=args.ignore_source)
    print(report(verdict))
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    sys.exit(main())
