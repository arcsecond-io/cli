import re

import pytest

from arcsecond.hosting import composedoc, network


@pytest.fixture(scope="module")
def manifest():
    return network.load()


def test_the_packaged_manifest_is_well_formed(manifest):
    assert manifest.version == 1
    assert manifest.destinations and manifest.listening and manifest.never_sent


def test_a_name_covers_its_sub_domains_and_nothing_else(manifest):
    assert manifest.find("licensing.arcsecond.io", 443).id == "licensing"
    assert manifest.find("Kafka2.gcn.nasa.gov.", 9092).id == "alerts-feed"
    assert manifest.find("a.tile.openstreetmap.org", 443).id == "browser-maps"
    # The right name on another port is another connection.
    assert manifest.find("kafka.gcn.nasa.gov", 443) is None
    # A look-alike is not a sub-domain.
    assert manifest.find("evil-licensing.arcsecond.io", 443) is None
    assert manifest.find("licensing.arcsecond.io.example.com", 443) is None


def test_who_opens_the_connection_narrows_the_answer(manifest):
    assert (
        manifest.find("statics.arcsecond.io", 443, origin="stack").id
        == "sky-brightness"
    )
    assert (
        manifest.find("statics.arcsecond.io", 443, origin="browser").id
        == "browser-arcsecond-statics"
    )
    assert manifest.find("server.arcgisonline.com", 443, origin="stack") is None


def test_a_default_installation_needs_one_name_and_only_one(manifest):
    """The headline of the network sheet. If this changes, the sheet's first
    sentence changes, and that is a decision, not a side effect."""
    required = [
        d
        for d in manifest.of("stack")
        if d.need == "required" and d.direction == "outbound"
    ]
    assert [d.names for d in required] == [("licensing.arcsecond.io",)]


def test_nothing_leaves_the_stack_unencrypted_except_to_servers_the_observatory_chose(
    manifest,
):
    plain = [
        d.id
        for d in manifest.of("stack")
        if d.direction == "outbound" and not d.encrypted
    ]
    assert plain == ["attached-storage"]


def test_the_listening_ports_are_the_ones_the_compose_file_publishes(manifest):
    """Two descriptions of the same thing; neither may drift from the other."""
    published = {}
    for service in composedoc.parse_services(network_compose_text()):
        for mapping in service.ports:
            parts = mapping.split(":")
            published[int(parts[-2])] = (
                "this machine only" if parts[0] == "127.0.0.1" else "every interface"
            )
    declared = {
        entry.port: entry.bound_to for entry in manifest.listening if not entry.optional
    }
    assert declared == published


def test_the_compose_file_names_the_alert_hosts_the_manifest_declares(manifest):
    comment = " ".join(
        line.strip().lstrip("# ")
        for line in network_compose_text().splitlines()
        if line.strip().startswith("#")
    )
    assert "auth.gcn.nasa.gov on 443" in comment
    assert re.search(
        r"kafka, kafka1, kafka2 and kafka3\.gcn\.nasa\.gov on 9092", comment
    )
    assert len(manifest.find("kafka.gcn.nasa.gov", 9092).names) == 4


def network_compose_text():
    from arcsecond.hosting.local import packaged_compose_text

    return packaged_compose_text()


@pytest.mark.parametrize(
    "broken, complaint",
    [
        ('from = "stack"', "not one of"),
        ("port = 443", "must be int"),
        ('purpose = "Activates', "is empty"),
    ],
)
def test_a_malformed_entry_is_refused_with_its_name(broken, complaint):
    text = network.packaged_text()
    replacements = {
        'from = "stack"': 'from = "somewhere"',
        "port = 443": 'port = "443"',
        'purpose = "Activates': 'purpose = ""\nx = "Activates',
    }
    assert broken in text
    with pytest.raises(network.ManifestError) as error:
        network.parse(text.replace(broken, replacements[broken], 1))
    assert complaint in str(error.value)


def test_an_id_cannot_be_used_twice():
    text = network.packaged_text().replace(
        'id = "catalogue-microlensing"', 'id = "licensing"', 1
    )
    with pytest.raises(network.ManifestError, match="used twice: licensing"):
        network.parse(text)


def test_the_text_an_administrator_reads_carries_no_acronym_soup(manifest):
    """Plain sentences. The few capitalised words allowed are proper names."""
    allowed = {"NASA", "ASCOM", "SIMBAD"}
    for d in manifest.destinations:
        for text in (d.purpose, d.feature, d.frequency, d.without_it, *d.data_sent):
            found = set(re.findall(r"\b[A-Z]{3,}\b", text)) - allowed
            assert not found, f"{d.id}: {found} in {text!r}"
