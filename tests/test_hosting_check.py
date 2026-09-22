"""`arcsecond check`: the parsers, the verdicts, and the command."""

import json

import pytest
from click.testing import CliRunner

from arcsecond.errors import ArcsecondError
from arcsecond.hosting import check, local, stack

# --- parsers ----------------------------------------------------------------

NETSTAT = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:5555           0.0.0.0:0              LISTENING       4711
  TCP    127.0.0.1:8800         0.0.0.0:0              LISTENING       4712
  TCP    192.168.1.42:49700     52.1.2.3:443           ESTABLISHED     1000
  TCP    [::]:5555              [::]:0                 LISTENING       4711
  UDP    0.0.0.0:5353           *:*                                    900
"""

LSOF = """COMMAND     PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
com.docke  1234 user   99u  IPv6 0x1     0t0  TCP *:5555 (LISTEN)
com.docke  1234 user  100u  IPv6 0x2     0t0  TCP *:8800 (LISTEN)
postgres   2222 user    7u  IPv4 0x3     0t0  TCP 127.0.0.1:5432 (LISTEN)
"""

SS = """State  Recv-Q Send-Q Local Address:Port  Peer Address:Port Process
LISTEN 0      4096         0.0.0.0:5555       0.0.0.0:*
LISTEN 0      4096       127.0.0.1:8800       0.0.0.0:*
LISTEN 0      4096            [::]:22            [::]:*
"""


def test_netstat_windows_keeps_only_listening_tcp():
    assert check.parse_netstat_windows(NETSTAT) == [
        ("0.0.0.0", 5555),
        ("127.0.0.1", 8800),
        ("[::]", 5555),
    ]


def test_lsof_and_ss_are_parsed():
    assert check.parse_lsof(LSOF) == [("*", 5555), ("*", 8800), ("127.0.0.1", 5432)]
    assert check.parse_ss(SS) == [("0.0.0.0", 5555), ("127.0.0.1", 8800), ("[::]", 22)]


def test_bind_classification():
    for host in ("0.0.0.0", "*", "[::]", "::"):
        assert check.bound_everywhere(host)
    for host in ("127.0.0.1", "[::1]", "localhost"):
        assert check.bound_to_loopback(host) and not check.bound_everywhere(host)


def test_powershell_json_one_or_many_or_none():
    assert check.parse_powershell_json("") == []
    assert check.parse_powershell_json('{"a": 1}') == [{"a": 1}]
    assert check.parse_powershell_json('[{"a": 1}, {"a": 2}]') == [{"a": 1}, {"a": 2}]
    assert check.parse_powershell_json("garbage") == []


def test_firewall_verdicts():
    assert check.firewall_verdict([]) == (check.FAIL, "no inbound rule allows TCP 5555")
    status, detail = check.firewall_verdict(
        [{"DisplayName": "Arcsecond", "Enabled": 1, "Profile": "Private"}]
    )
    assert status == check.OK and "Arcsecond" in detail
    status, _ = check.firewall_verdict(
        [{"DisplayName": "x", "Enabled": "True", "Profile": "Any"}]
    )
    assert status == check.OK
    status, detail = check.firewall_verdict(
        [{"DisplayName": "x", "Enabled": 2, "Profile": "Private"}]
    )
    assert status == check.FAIL and "none enabled" in detail
    status, _ = check.firewall_verdict(
        [{"DisplayName": "x", "Enabled": 1, "Profile": "Public"}]
    )
    assert status == check.FAIL


def test_network_profile_verdicts():
    assert check.network_profile_verdict([])[0] == check.WARN
    assert (
        check.network_profile_verdict([{"Name": "Home", "NetworkCategory": 1}])[0]
        == check.OK
    )
    status, detail = check.network_profile_verdict(
        [{"Name": "Observatory", "NetworkCategory": 0}]
    )
    assert status == check.FAIL and "Observatory" in detail
    assert (
        check.network_profile_verdict([{"Name": "x", "NetworkCategory": "Public"}])[0]
        == check.FAIL
    )


# --- a fake machine -------------------------------------------------------------


class FakeHost(check.Host):
    def __init__(
        self,
        platform="darwin",
        sockets=None,
        lan="10.0.0.77",
        http=None,
        admin=False,
        powershell=None,
    ):
        self.platform = platform
        self._sockets = sockets
        self._lan = lan
        self._http = http or {}
        self._admin = admin
        self._powershell = powershell or {}
        self.powershell_calls = []

    def listening_sockets(self):
        return self._sockets

    def lan_ipv4(self):
        return self._lan

    def http_ok(self, url):
        return self._http.get(url)

    def is_admin(self):
        return self._admin

    def powershell(self, script):
        self.powershell_calls.append(script)
        for needle, answer in self._powershell.items():
            if needle in script:
                return answer
        return None


@pytest.fixture
def install(tmp_path, monkeypatch):
    keys = (
        "\n".join(
            f"{k}=value"
            for k in local.REQUIRED_ENV_PROVIDERS
            if k != local.FRONTEND_HOST_ENV_KEY
        )
        + "\nHOSTED_FRONTEND_HOST=10.0.0.77:5555\n"
    )
    (tmp_path / ".env").write_text(keys)
    version = local._compose_version(local.packaged_compose_text())
    (tmp_path / "docker-compose.yml").write_text(
        f"# Version {version}\nservices: {{}}\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(stack, "ensure_docker", lambda: "2.29")
    monkeypatch.setattr(
        stack,
        "services_status",
        lambda install: [
            {"Service": "backend", "State": "running", "Health": "healthy"},
            {"Service": "web", "State": "running", "Health": ""},
        ],
    )
    from arcsecond.imagesources import autostart
    from arcsecond.imagesources import commands as cameras
    from arcsecond.imagesources import store

    monkeypatch.setattr(store, "all_cameras", lambda: [])
    monkeypatch.setattr(cameras, "_running_proxy_port", lambda: None)
    monkeypatch.setattr(autostart, "is_enabled", lambda: False)
    return stack.InstallDir(tmp_path)


HEALTHY = {"http://localhost:8800/healthcheck/": 200, "http://localhost:5555/": 200}
OPEN = [("*", 5555), ("*", 8800)]


def _by_key(findings):
    return {f.key: f for f in findings}


def test_a_healthy_reachable_install_has_no_failure(install):
    findings = _by_key(check.run_checks(install, FakeHost(sockets=OPEN, http=HEALTHY)))
    assert not [k for k, f in findings.items() if f.status == check.FAIL]
    assert findings["ports.5555"].status == check.OK
    assert findings["answers.api"].status == check.OK
    assert findings["lan.host"].status == check.OK
    assert findings["lan.host"].detail == "http://10.0.0.77:5555"


def test_a_loopback_bound_port_is_the_failure_it_is(install):
    host = FakeHost(sockets=[("127.0.0.1", 5555), ("*", 8800)], http=HEALTHY)
    findings = _by_key(check.run_checks(install, host))
    assert findings["ports.5555"].status == check.FAIL
    assert "this machine alone" in findings["ports.5555"].detail


def test_nothing_listening_is_a_failure_only_when_containers_run(install, monkeypatch):
    findings = _by_key(check.run_checks(install, FakeHost(sockets=[], http={})))
    assert findings["ports.5555"].status == check.FAIL
    monkeypatch.setattr(stack, "services_status", lambda install: [])
    findings = _by_key(check.run_checks(install, FakeHost(sockets=[], http={})))
    assert (
        findings["containers"].status == check.FAIL
        and findings["containers"].fix == "arcsecond start"
    )
    assert findings["ports.5555"].status == check.WARN
    assert "answers.api" not in findings


def test_an_undeclared_lan_host_says_what_it_costs_and_how_to_fix_it(install):
    (install.path / ".env").write_text(
        "\n".join(
            f"{k}=value"
            for k in local.REQUIRED_ENV_PROVIDERS
            if k != local.FRONTEND_HOST_ENV_KEY
        )
        + "\nHOSTED_FRONTEND_HOST=\n"
    )
    finding = check.check_lan_host(install, FakeHost(lan="192.168.1.42"))
    assert finding.status == check.WARN
    assert "localhost" in finding.detail
    assert "arcsecond setup --lan-host 192.168.1.42" in finding.fix


def test_a_lan_host_that_no_longer_matches_the_machine_is_flagged(install):
    finding = check.check_lan_host(install, FakeHost(lan="10.0.0.99"))
    assert finding.status == check.WARN
    assert "10.0.0.99" in finding.detail and "reboot" in finding.detail


def test_a_named_lan_host_is_not_compared_to_the_ip(install):
    (install.path / ".env").write_text("HOSTED_FRONTEND_HOST=arcsecond.local:5555\n")
    assert check.check_lan_host(install, FakeHost(lan="10.0.0.99")).status == check.OK


def test_env_file_checks(install):
    (install.path / ".env").write_text("SECRET_KEY=abc$def\nPOSTGRES_USER=x\n")
    findings = _by_key(check.check_env_file(install))
    assert (
        findings["env.keys"].status == check.WARN
        and "AUTH_JWT_SIGNING_KEY" in findings["env.keys"].detail
    )
    assert (
        findings["env.secrets"].status == check.WARN
        and "SECRET_KEY" in findings["env.secrets"].detail
    )


def test_docker_unavailable_stops_the_container_checks(install, monkeypatch):
    def down():
        raise ArcsecondError(stack.DOCKER_NOT_RUNNING)

    monkeypatch.setattr(stack, "ensure_docker", down)
    findings = _by_key(check.run_checks(install, FakeHost(sockets=[], http={})))
    assert findings["docker"].status == check.FAIL
    assert "Docker Desktop" in (findings["docker"].fix or "")
    assert not any(k.startswith("containers") for k in findings)


def test_an_outdated_template_points_at_update(install):
    (install.path / "docker-compose.yml").write_text("# Version 1.0\nservices: {}\n")
    assert check.check_template(install).fix == "arcsecond update"


# --- windows --------------------------------------------------------------------

PS_PUBLIC = json.dumps(
    {"Name": "Observatory WiFi", "InterfaceAlias": "Wi-Fi", "NetworkCategory": 0}
)
PS_PRIVATE = json.dumps(
    {"Name": "Home", "InterfaceAlias": "Wi-Fi", "NetworkCategory": 1}
)
PS_RULE = json.dumps(
    {"DisplayName": "Arcsecond.local (TCP 5555)", "Enabled": 1, "Profile": "Private"}
)


def test_windows_profile_and_firewall_are_read_not_probed(install):
    host = FakeHost(
        platform="win32",
        sockets=OPEN,
        http=HEALTHY,
        powershell={
            "Get-NetConnectionProfile": PS_PUBLIC,
            "Get-NetFirewallPortFilter": "",
        },
    )
    findings = _by_key(check.run_checks(install, host))
    assert (
        findings["windows.profile"].status == check.FAIL
        and "Observatory WiFi" in findings["windows.profile"].detail
    )
    assert "Private" in findings["windows.profile"].fix
    assert findings["windows.firewall"].status == check.FAIL
    assert check.FIREWALL_FIX in findings["windows.firewall"].fix
    assert "cannot test its own firewall" in findings["windows.firewall"].data["note"]
    assert "windows.firewall.fix" not in findings  # no --fix asked


def test_windows_all_green(install):
    host = FakeHost(
        platform="win32",
        sockets=OPEN,
        http=HEALTHY,
        powershell={
            "Get-NetConnectionProfile": PS_PRIVATE,
            "Get-NetFirewallPortFilter": PS_RULE,
        },
    )
    findings = _by_key(check.run_checks(install, host))
    assert findings["windows.profile"].status == check.OK
    assert findings["windows.firewall"].status == check.OK


def test_fix_prints_the_command_without_admin_and_runs_it_with(install):
    host = FakeHost(
        platform="win32",
        sockets=OPEN,
        http=HEALTHY,
        admin=False,
        powershell={
            "Get-NetConnectionProfile": PS_PRIVATE,
            "Get-NetFirewallPortFilter": "",
        },
    )
    findings = _by_key(check.run_checks(install, host, fix=True))
    assert findings["windows.firewall.fix"].status == check.SKIP
    assert not any("New-NetFirewallRule" in s for s in host.powershell_calls)

    host = FakeHost(
        platform="win32",
        sockets=OPEN,
        http=HEALTHY,
        admin=True,
        powershell={
            "Get-NetConnectionProfile": PS_PRIVATE,
            "Get-NetFirewallPortFilter": "",
            "New-NetFirewallRule": "ok",
        },
    )
    findings = _by_key(check.run_checks(install, host, fix=True))
    assert findings["windows.firewall.fix"].status == check.OK
    assert any("New-NetFirewallRule" in s for s in host.powershell_calls)


def test_no_windows_checks_elsewhere(install):
    findings = _by_key(
        check.run_checks(
            install, FakeHost(platform="linux", sockets=OPEN, http=HEALTHY)
        )
    )
    assert not any(k.startswith("windows") for k in findings)


def test_the_network_profile_is_never_changed_by_fix(install):
    host = FakeHost(
        platform="win32",
        sockets=OPEN,
        http=HEALTHY,
        admin=True,
        powershell={
            "Get-NetConnectionProfile": PS_PUBLIC,
            "Get-NetFirewallPortFilter": PS_RULE,
        },
    )
    check.run_checks(install, host, fix=True)
    assert not any("Set-NetConnectionProfile" in s for s in host.powershell_calls)


# --- the proxy --------------------------------------------------------------------


def test_env_var_camera_passwords_are_flagged_when_autostart_is_on(
    install, monkeypatch
):
    from arcsecond.imagesources import autostart
    from arcsecond.imagesources import commands as cameras
    from arcsecond.imagesources import store
    from arcsecond.imagesources.store import Camera

    monkeypatch.setattr(
        store,
        "all_cameras",
        lambda: [
            Camera(id="dome", kind="net", url="rtsp://u:${CAM_PW}@cam/s"),
            Camera(id="sky", kind="allsky", path="/x.jpg"),
        ],
    )
    monkeypatch.setattr(cameras, "_running_proxy_port", lambda: 8765)
    monkeypatch.setattr(autostart, "is_enabled", lambda: True)
    findings = _by_key(check.check_proxy())
    assert (
        findings["proxy"].status == check.OK
        and "starts at login" in findings["proxy"].detail
    )
    assert (
        findings["proxy.passwords"].status == check.WARN
        and "dome" in findings["proxy.passwords"].detail
    )

    monkeypatch.setattr(autostart, "is_enabled", lambda: False)
    assert "proxy.passwords" not in _by_key(check.check_proxy())


# --- the command ----------------------------------------------------------------------


def test_the_command_prints_marks_remedies_and_the_lan_url(install, monkeypatch):
    monkeypatch.setattr(
        check,
        "Host",
        lambda: FakeHost(sockets=[("127.0.0.1", 5555), ("*", 8800)], http=HEALTHY),
    )
    result = CliRunner().invoke(check.check_cmd)
    assert result.exit_code == 1, result.output
    assert "✗" in result.output and "→" in result.output
    assert "problem(s)" in result.output
    assert "http://10.0.0.77:5555" in result.output


def test_the_command_exits_zero_when_nothing_fails(install, monkeypatch):
    monkeypatch.setattr(check, "Host", lambda: FakeHost(sockets=OPEN, http=HEALTHY))
    result = CliRunner().invoke(check.check_cmd)
    assert result.exit_code == 0, result.output


def test_json_output_is_structured(install, monkeypatch):
    monkeypatch.setattr(check, "Host", lambda: FakeHost(sockets=OPEN, http=HEALTHY))
    result = CliRunner().invoke(check.check_cmd, ["--json"])
    payload = json.loads(result.output)
    assert payload["installation"] == str(install.path)
    assert payload["platform"] == "darwin"
    keys = {f["key"] for f in payload["findings"]}
    assert {"docker", "template", "lan.host", "ports.5555", "api"} <= keys
    assert all(
        {"key", "label", "status", "detail", "fix", "data"} <= set(f)
        for f in payload["findings"]
    )


def test_check_is_mounted():
    from arcsecond import cli

    assert "check" in cli.main.commands
