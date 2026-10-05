"""The one-page network sheet, generated from the manifest.

What an observatory hands to whoever runs its network: what listens, what
is contacted and why, what never leaves, how to check. Every word of it that
states a fact comes out of `manifest.toml`; nothing is written here that the
manifest could contradict.

Three renderings of the same content: Markdown for the documentation, a
self-contained page that prints on one sheet of A4 (and so to a PDF, from
any browser), and a plain-text firewall request to paste into a ticket.

One page is a constraint, not a hope: `LINE_BUDGET` is what fits, the
manifest holds each line to a length, and a test counts.
"""

import html
from dataclasses import dataclass
from typing import List, Tuple

from . import Destination, Manifest

# Lines of 8.5-point text the A4 page holds below its title, measured by
# printing it: 64 lines filled 93% of the printable height. The test fails
# before the printer does.
LINE_BUDGET = 68
# Characters of a destination cell before it wraps onto a second line.
NAME_CELL = 58

DOCTOR = "arcsecond doctor"
SHEET_ADDRESS = "docs.arcsecond.io/reference/network"


@dataclass(frozen=True)
class Group:
    title: str
    lead: str
    rows: Tuple[Destination, ...]


def names_of(entry: Destination) -> str:
    """The entry's names on one line; hosts of one domain share its ending."""
    names = list(entry.names)
    if not names:
        if entry.direction == "outbound":
            return "a server you choose"
        return (
            "a broadcast on your network"
            if entry.transport == "udp"
            else "addresses you enter"
        )
    if len(names) > 2:
        tails = {n.split(".", 1)[1] for n in names if "." in n}
        if len(tails) == 1:
            return ", ".join(n.split(".", 1)[0] for n in names) + f" .{tails.pop()}"
    return ", ".join(names)


def port_of(entry: Destination) -> str:
    if entry.ports_note:
        return entry.ports_note
    return f"{entry.port}" if entry.transport == "tcp" else f"{entry.port} (datagram)"


def groups(manifest: Manifest) -> List[Group]:
    stack = [d for d in manifest.of("stack") if d.direction == "outbound"]
    required = tuple(d for d in stack if d.always_on and d.need == "required")
    works_without = tuple(d for d in stack if d.always_on and d.need != "required")
    switched_on = tuple(d for d in stack if not d.always_on)
    install = tuple(
        manifest.of("docker")
        + [d for d in manifest.of("tool") if d.direction == "outbound"]
    )
    browser = tuple(manifest.of("browser"))
    local = tuple(d for d in manifest.destinations if d.direction == "local-network")
    return [
        Group("Required", "Outbound, encrypted.", required),
        Group(
            "Public catalogues and lookups",
            "Outbound, encrypted. The installation runs without them, with less to show.",
            works_without,
        ),
        Group(
            "Only when you turn the feature on",
            "Outbound. Nothing here is contacted by a default installation.",
            switched_on,
        ),
        Group(
            "To install and to update",
            "Outbound, encrypted. Not needed while running.",
            install,
        ),
        Group(
            "From your users' browsers",
            "Outbound, encrypted, from their workstations, not from the installation.",
            browser,
        ),
        Group("On your local network only", "Never leaves the site.", local),
    ]


def headline(manifest: Manifest) -> str:
    stack = [d for d in manifest.of("stack") if d.direction == "outbound"]
    required = [d for d in stack if d.always_on and d.need == "required"]
    others = [d for d in stack if d.always_on and d.need != "required"]
    network_ports = [
        p
        for p in manifest.listening
        if p.bound_to == "every interface" and not p.optional
    ]
    required_text = " and ".join(f"{names_of(d)} on port {d.port}" for d in required)
    other_ports = sorted({d.port for d in others})
    ports_text = (
        f"port {other_ports[0]}"
        if len(other_ports) == 1
        else "ports " + ", ".join(map(str, other_ports))
    )
    return (
        f"Arcsecond.local listens on {_count(len(network_ports))} port of your local network "
        f"({', '.join(str(p.port) for p in network_ports)}) and on nothing from the Internet side. "
        f"Everything else is outbound. One destination is required: {required_text}. "
        f"A default installation also looks up {len(others)} public astronomy services, all on {ports_text}, "
        "and runs without them. The rest exists only when you turn a feature on."
    )


def _count(n: int) -> str:
    return {1: "one", 2: "two", 3: "three"}.get(n, str(n))


def listening_lines(manifest: Manifest) -> List[str]:
    lines = []
    for p in manifest.listening:
        optional = " Optional." if p.optional else ""
        lines.append(
            f"Port {p.port}, {p.bound_to}: {_first_sentence(p.purpose)}{optional}"
        )
    return lines


def _first_sentence(text: str) -> str:
    return text.split(": ", 1)[0].rstrip(".") + "." if ": " in text else text


CUT_OFF = (
    "An activated installation keeps operating with no outside connection at all: "
    "instrument control and data recording are local. It only does without the lookups listed above."
)


def verify_lines(manifest: Manifest) -> List[str]:
    return [
        f"Run `{DOCTOR}` on the machine: it tests every destination above and sends nothing about your observatory. "
        f"`{DOCTOR} --report` writes the result to a file for your records.",
        f"This sheet is generated from the software's own network manifest (audited {manifest.audited}); "
        f"the current version is at {SHEET_ADDRESS}.",
        f"Security questions: {manifest.contact}",
    ]


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def render_markdown(manifest: Manifest) -> str:
    out = [
        "# Arcsecond.local on your network",
        "",
        headline(manifest),
        "",
        "## What listens",
        "",
    ]
    out += [f"- {line}" for line in listening_lines(manifest)]
    out += ["", "## What it contacts", ""]
    for group in groups(manifest):
        if not group.rows:
            continue
        out += [
            f"**{group.title}.** {group.lead}",
            "",
            "| Destination | Port | What for |",
            "| --- | --- | --- |",
        ]
        out += [f"| {names_of(d)} | {port_of(d)} | {d.short} |" for d in group.rows]
        out.append("")
    out += ["## What never leaves the site", ""]
    out += [f"- {item[0].upper() + item[1:]}" for item in manifest.never_sent]
    out += [
        "",
        "## If the connection is cut",
        "",
        CUT_OFF,
        "",
        "## Check it yourself",
        "",
    ]
    out += [f"- {line}" for line in verify_lines(manifest)]
    return "\n".join(out) + "\n"


def printed_lines(manifest: Manifest) -> int:
    """How many lines the printed page takes: what the one-page test counts.
    A table row is one line; a paragraph wraps at the page's width."""
    width = 150  # characters of 8.5-point text across the page
    wrap = lambda text: max(1, -(-len(text) // width))  # noqa: E731
    lines = wrap(headline(manifest)) + 1
    lines += 1 + len(manifest.listening)
    for group in groups(manifest):
        if group.rows:
            lines += 1 + sum(1 + (len(names_of(d)) > NAME_CELL) for d in group.rows)
    lines += 1 + -(-len(manifest.never_sent) // 2)  # two columns
    lines += 1 + wrap(CUT_OFF)
    lines += 1 + sum(wrap(line) for line in verify_lines(manifest))
    return lines + 7  # the gaps between sections


# ---------------------------------------------------------------------------
# A page that prints on one sheet
# ---------------------------------------------------------------------------

_STYLE = """
@page { size: A4; margin: 11mm 12mm; }
* { box-sizing: border-box; }
body { font: 8.5pt/1.25 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #111; margin: 0; }
h1 { font-size: 15pt; margin: 0 0 2mm; }
h2 { font-size: 9pt; text-transform: uppercase; letter-spacing: .04em; margin: 2.2mm 0 .6mm; color: #333; }
p { margin: 0 0 1mm; }
.lead { font-size: 9.5pt; }
table { width: 100%; border-collapse: collapse; }
td { padding: 0 2mm 0 0; vertical-align: top; }
td.name { width: 52%; font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 7.6pt; }
td.port { width: 14%; }
tr.group td { padding-top: 1.4mm; font-weight: 600; }
tr.group span { font-weight: 400; color: #444; }
ul { margin: 0; padding-left: 4mm; }
ul.two { columns: 2; }
footer { margin-top: 2mm; color: #444; }
code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 7.8pt; }
"""


def _inline(text: str) -> str:
    parts = html.escape(text).split("`")
    return "".join(f"<code>{p}</code>" if i % 2 else p for i, p in enumerate(parts))


def render_html(manifest: Manifest) -> str:
    e = html.escape
    rows = []
    for group in groups(manifest):
        if not group.rows:
            continue
        rows.append(
            f'<tr class="group"><td colspan="3">{e(group.title)}. <span>{e(group.lead)}</span></td></tr>'
        )
        rows += [
            f'<tr><td class="name">{e(names_of(d))}</td><td class="port">{e(port_of(d))}</td><td>{e(d.short)}</td></tr>'
            for d in group.rows
        ]
    listening = "".join(f"<li>{e(line)}</li>" for line in listening_lines(manifest))
    never = "".join(
        f"<li>{e(item[0].upper() + item[1:])}</li>" for item in manifest.never_sent
    )
    verify = "".join(f"<li>{_inline(line)}</li>" for line in verify_lines(manifest))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Arcsecond.local on your network</title>
<style>{_STYLE}</style></head>
<body>
<h1>Arcsecond.local on your network</h1>
<p class="lead">{e(headline(manifest))}</p>
<h2>What listens</h2>
<ul>{listening}</ul>
<h2>What it contacts</h2>
<table>{''.join(rows)}</table>
<h2>What never leaves the site</h2>
<ul class="two">{never}</ul>
<h2>If the connection is cut</h2>
<p>{e(CUT_OFF)}</p>
<h2>Check it yourself</h2>
<ul>{verify}</ul>
</body></html>
"""


# ---------------------------------------------------------------------------
# The firewall request
# ---------------------------------------------------------------------------


def render_firewall_request(manifest: Manifest) -> str:
    """Plain text for a ticket: the request in words, then the same thing as
    lists a firewall or a web proxy takes."""
    by_title = {g.title: g for g in groups(manifest)}
    required = by_title["Required"].rows
    catalogues = by_title["Public catalogues and lookups"].rows
    features = [
        d for d in by_title["Only when you turn the feature on"].rows if d.names
    ]
    install = by_title["To install and to update"].rows

    def listing(entries) -> List[str]:
        return [
            f"  {name:<40} {d.transport} {d.port:<6} {d.short}"
            for d in entries
            for name in d.names
        ]

    out = [
        "Request: outbound access for Arcsecond.local",
        "",
        "We run Arcsecond.local, observatory software, on one machine of our network.",
        "It accepts no connection from the Internet and needs no port forwarded.",
        "It opens outbound connections only, encrypted, to the destinations below.",
        "Please allow them from that machine.",
        "",
        "Required:",
        *listing(required),
        "",
        "To install and to update the software:",
        *listing(install),
        "",
        "Recommended (public astronomy catalogues; the software runs without them):",
        *listing(catalogues),
        "",
        "Only for features we may turn on:",
        *listing(features),
        "",
        "Note: port 9092 carries NASA's alert feed. It is not web traffic and cannot go through a web proxy.",
        "",
        "--- as a web proxy allow list (names reached on port 443) ---",
        *sorted(
            {
                name
                for d in (*required, *install, *catalogues, *features)
                if d.port == 443
                for name in d.names
            }
        ),
        "",
        f"The software's own check, `{DOCTOR}`, tests each of these and sends nothing about the observatory.",
        f"Source: the network manifest shipped with the software, audited {manifest.audited}.",
    ]
    return "\n".join(out) + "\n"


PAGE = "index.md"
PRINTABLE = "network-sheet.html"
REQUEST = "firewall-request.txt"
# Printed from PRINTABLE when the documentation is deployed
# (scripts/network-sheet-pdf.mjs in the documentation repository).
PDF = "arcsecond-local-network-sheet.pdf"
STATIC_ADDRESS = "/network"  # where the documentation site serves the two files below


def generate_page(manifest: Manifest) -> dict:
    """The documentation page: the sheet, then where its other forms are."""
    also = [
        "## To print, and to paste",
        "",
        f"- [The same sheet as a one-page PDF]({STATIC_ADDRESS}/{PDF}).",
        f"- [The same sheet on one printable page]({STATIC_ADDRESS}/{PRINTABLE}), to print from your browser.",
        f"- [The request to send to whoever runs your firewall]({STATIC_ADDRESS}/{REQUEST}), as plain text.",
        "",
    ]
    return {PAGE: _frontmatter() + render_markdown(manifest) + "\n" + "\n".join(also)}


def generate_static(manifest: Manifest) -> dict:
    return {
        PRINTABLE: render_html(manifest),
        REQUEST: render_firewall_request(manifest),
    }


def _frontmatter() -> str:
    lines = [
        "---",
        'title: "Arcsecond.local on your network"',
        "visibility: public",
        "audience: admin",
        "tier: reference",
        "source: generated",
        "---",
    ]
    return "\n".join(lines) + "\n\n"
