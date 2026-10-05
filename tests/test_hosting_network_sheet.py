import re

from click.testing import CliRunner

from arcsecond import docgen
from arcsecond.hosting import network
from arcsecond.hosting.network import sheet


def _manifest():
    return network.load()


def test_the_sheet_fits_on_one_page():
    """Measured once by printing it (see LINE_BUDGET). A manifest that grows
    past the page fails here, where a line can still be shortened or an entry
    questioned, rather than at an administrator's printer."""
    assert sheet.printed_lines(_manifest()) <= sheet.LINE_BUDGET


def test_the_headline_is_computed_not_written():
    text = sheet.headline(_manifest())
    assert "listens on one port of your local network (5555)" in text
    assert "One destination is required: licensing.arcsecond.io on port 443." in text
    assert "10 public astronomy services, all on port 443" in text

    # Publish a second port to the network, and the first sentence follows.
    widened = network.parse(
        network.packaged_text().replace(
            'bound_to = "this machine only"', 'bound_to = "every interface"'
        )
    )
    assert "listens on two port" in sheet.headline(
        widened
    ) and "(5555, 8800)" in sheet.headline(widened)


def test_every_destination_of_the_manifest_is_on_the_sheet_once():
    manifest = _manifest()
    listed = [d.id for group in sheet.groups(manifest) for d in group.rows]
    assert sorted(listed) == sorted(d.id for d in manifest.destinations)


def test_the_groups_say_what_is_needed_and_what_is_not():
    by_title = {g.title: [d.id for d in g.rows] for g in sheet.groups(_manifest())}
    assert by_title["Required"] == ["licensing"]
    assert "alerts-feed" in by_title["Only when you turn the feature on"]
    assert "catalogue-objects" in by_title["Public catalogues and lookups"]
    assert by_title["On your local network only"] == [
        "instruments",
        "instrument-discovery",
        "cameras",
    ]


def test_hosts_of_one_domain_share_a_line():
    manifest = _manifest()
    assert (
        sheet.names_of(manifest.find("kafka.gcn.nasa.gov", 9092))
        == "kafka, kafka1, kafka2, kafka3 .gcn.nasa.gov"
    )
    by_id = {d.id: d for d in manifest.destinations}
    assert sheet.names_of(by_id["outgoing-mail"]) == "a server you choose"
    assert sheet.port_of(by_id["outgoing-mail"]) == "587, 465 or 25"
    assert (
        sheet.names_of(by_id["instrument-discovery"]) == "a broadcast on your network"
    )


def test_the_three_forms_say_the_same_things():
    manifest = _manifest()
    markdown = sheet.render_markdown(manifest)
    page = sheet.render_html(manifest)
    for d in manifest.destinations:
        assert d.short in markdown and d.short in page.replace("&#x27;", "'"), d.id
    for item in manifest.never_sent:
        assert item[1:] in markdown and item[1:] in page.replace("&#x27;", "'")
    assert manifest.contact in markdown and manifest.contact in page


def test_the_sheet_has_no_acronym_soup_and_no_slogan():
    text = sheet.render_markdown(_manifest())
    allowed = {"NASA", "OGLE", "SIMBAD"}
    assert set(re.findall(r"\b[A-Z]{3,}\b", text)) <= allowed
    for slogan in ("one port, nothing special", "fully compliant", "IT-friendly"):
        assert slogan not in text


def test_the_firewall_request_lists_every_name_with_its_port():
    manifest = _manifest()
    request = sheet.render_firewall_request(manifest)
    assert re.search(r"licensing\.arcsecond\.io\s+tcp 443", request)
    assert re.search(r"kafka2\.gcn\.nasa\.gov\s+tcp 9092", request)
    assert "cannot go through a web proxy" in request
    allow_list = (
        request.split(
            "--- as a web proxy allow list (names reached on port 443) ---\n"
        )[1]
        .split("\n\n")[0]
        .splitlines()
    )
    assert "licensing.arcsecond.io" in allow_list and "ghcr.io" in allow_list
    assert not any(
        "kafka" in name for name in allow_list
    )  # 9092 is not the proxy's to carry
    # The browsers' destinations are the workstations' business, not this machine's.
    assert "server.arcgisonline.com" not in request


def test_docs_network_writes_then_checks(tmp_path):
    out, static = tmp_path / "page", tmp_path / "static"
    args = ["network", "--out", str(out), "--static", str(static)]
    written = CliRunner().invoke(docgen.docs, args)
    assert written.exit_code == 0, written.output
    assert (out / "index.md").read_text().startswith("---\ntitle:")
    assert (static / "network-sheet.html").exists() and (
        static / "firewall-request.txt"
    ).exists()
    assert CliRunner().invoke(docgen.docs, [*args, "--check"]).exit_code == 0

    (static / "firewall-request.txt").write_text("edited by hand")
    stale = CliRunner().invoke(docgen.docs, [*args, "--check"])
    assert stale.exit_code == 1 and "firewall-request.txt" in stale.output
