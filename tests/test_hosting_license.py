"""`arcsecond license`: the backend's own view of the license, and why it is wrong.

The probe itself runs the backend's code inside the container, so here it is a
string to build and an answer to parse; what is tested is the reading of that
answer, and that the command reaches the right container the right way.
"""

import json
import subprocess

import pytest
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.errors import ArcsecondError
from arcsecond.hosting import license as lic
from arcsecond.hosting import stack

EMAIL = "director@observatory.example"


def _report(**overrides):
    report = {
        "errors": [],
        "service_url": "https://licensing.arcsecond.io",
        "installations": [
            {
                "id": 1,
                "mode": "LOCAL",
                "fingerprint": "abcdef12... (64 chars)",
                "is_local": True,
            }
        ],
        "licenses": [],
        "local": {
            "id": 1,
            "has_fingerprint": True,
            "has_valid_license": False,
            "email_verification_pending": False,
            "setup_blocked": False,
        },
        "owner_addresses": [
            {"username": "admin", "email": EMAIL, "primary": True, "verified": True}
        ],
        "mint_email": EMAIL,
        "validations": [],
        "log": [],
    }
    report.update(overrides)
    return report


def _licence(**overrides):
    row = {
        "id": 7,
        "installation": 1,
        "email": EMAIL,
        "is_trial": True,
        "status": "ACTIVE",
        "expiry": "2027-01-01T00:00:00+00:00",
        "has_key": True,
        "is_valid": True,
    }
    row.update(overrides)
    return row


def _levels(findings):
    return [level for level, _ in findings]


def _text(findings):
    return "\n".join(text for _, text in findings)


# -- the probe ----------------------------------------------------------------


def test_the_probe_is_valid_python_whatever_the_flags():
    for validate in (True, False):
        for sync in (True, False):
            source = lic.build_probe(validate, sync)
            compile(source, "<probe>", "exec")
            assert f"VALIDATE = {validate}" in source
            assert f"SYNC = {sync}" in source


def test_the_probe_never_reads_out_the_key_or_the_whole_fingerprint():
    source = lic.build_probe(True, True)
    assert "'has_key': bool(l.keygen_license_key)" in source
    assert "'key':" not in source
    assert "_mask(i.machine_fingerprint)" in source


def test_the_answer_is_found_after_whatever_django_printed_first():
    out = (
        "12 objects imported automatically\n"
        + lic.MARK
        + json.dumps({"errors": []})
        + "\n"
    )
    assert lic.parse_probe_output(out) == {"errors": []}


def test_no_answer_is_an_error_that_shows_what_came_back():
    with pytest.raises(ArcsecondError) as raised:
        lic.parse_probe_output("Traceback: something broke")
    assert "something broke" in str(raised.value)


# -- the reading ----------------------------------------------------------------


def test_verified_owner_and_no_licence_is_the_utah_box():
    findings = lic.diagnose(_report(), worker_running=True)
    assert _levels(findings)[0] == lic.FAIL
    text = _text(findings)
    assert EMAIL in text
    assert "No license found" in text and "Activated" in text
    assert "arcsecond license sync" in text
    assert lic.exit_code(findings) == 2


def test_no_verified_owner_sends_them_to_finish_activation():
    findings = lic.diagnose(_report(mint_email=None), worker_running=True)
    assert "Finish activation" in _text(findings)


def test_a_valid_licence_is_said_so_and_exits_zero():
    report = _report(
        licenses=[_licence()],
        local={**_report()["local"], "has_valid_license": True},
        validations=[
            {"license": 7, "valid": True, "status": "ACTIVE", "code": "VALID"}
        ],
    )
    findings = lic.diagnose(report, worker_running=True)
    assert _levels(findings) == [lic.OK, lic.OK]
    assert "expires 2027-01-01" in _text(findings)
    assert lic.exit_code(findings) == 0


def test_a_licence_on_another_installation_record_is_named():
    report = _report(
        installations=[
            {"id": 1, "mode": "LOCAL", "fingerprint": "", "is_local": True},
            {"id": 2, "mode": "LOCAL", "fingerprint": "", "is_local": False},
        ],
        licenses=[_licence(installation=2)],
    )
    text = _text(lic.diagnose(report, worker_running=True))
    assert "2 installation records" in text
    assert "belongs to installation #2, not to #1" in text


def test_bound_to_another_machine_says_how_to_move_it_here():
    report = _report(
        licenses=[_licence()],
        local={**_report()["local"], "has_valid_license": True},
        validations=[
            {
                "license": 7,
                "valid": False,
                "status": "ACTIVE",
                "code": "FINGERPRINT_SCOPE_MISMATCH",
            }
        ],
    )
    findings = lic.diagnose(report, worker_running=True)
    text = _text(findings)
    assert "bound to another machine" in text
    assert "Request the license again" in text
    assert lic.exit_code(findings) == 2


def test_an_unanswered_validation_is_a_warning_not_a_verdict():
    report = _report(
        licenses=[_licence()],
        local={**_report()["local"], "has_valid_license": True},
        validations=[
            {"license": 7, "valid": False, "code": "unreachable", "cause": "timeout"}
        ],
    )
    findings = lic.diagnose(report, worker_running=True)
    assert (lic.WARN, next(t for _, t in findings if "no verdict" in t)) in findings
    assert "timeout" in _text(findings)
    assert lic.exit_code(findings) == 1


def test_inactive_at_keygen_is_explained_and_a_stale_record_is_noticed():
    report = _report(
        licenses=[_licence(status="ACTIVE")],
        local={**_report()["local"], "has_valid_license": True},
        validations=[
            {"license": 7, "valid": True, "status": "INACTIVE", "code": "VALID"}
        ],
    )
    text = _text(lic.diagnose(report, worker_running=True))
    assert "Keygen says INACTIVE" in text
    assert "90 days" in text


@pytest.mark.parametrize(
    "answer, expected",
    [
        (
            'License mint failed: HTTP 403 {"detail": "the license for this address is active on '
            'another installation; verify the address from this one to move it here"}',
            "held by another installation",
        ),
        (
            'License mint failed: HTTP 403 {"detail": "email address has not been verified"}',
            "never seen the owner address verified",
        ),
        (
            'License mint failed: HTTP 409 {"detail": "elsewhere"}',
            "another licensing environment",
        ),
        ("License mint request failed: ConnectionError: boom", "could not be reached"),
    ],
)
def test_sync_turns_the_services_refusal_into_a_sentence(answer, expected):
    report = _report(synced=True, log=[{"level": "WARNING", "message": answer}])
    text = _text(lic.diagnose(report, worker_running=True))
    assert expected in text
    assert answer in text


def test_a_stopped_worker_explains_why_nothing_ever_synced():
    findings = lic.diagnose(_report(), worker_running=False)
    assert "arcsecond-worker container is not running" in _text(findings)


def test_no_local_installation_stops_there():
    findings = lic.diagnose(_report(local=None))
    assert _levels(findings) == [lic.FAIL]
    assert "first boot" in _text(findings)


# -- the command ------------------------------------------------------------------


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setattr(stack, "ensure_docker", lambda: "2.29")
    monkeypatch.setattr(lic, "_container_running", lambda name: True)
    calls = []
    answer = {"report": _report()}

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd, 0, stdout=lic.MARK + json.dumps(answer["report"]) + "\n", stderr=""
        )

    monkeypatch.setattr(lic.subprocess, "run", fake_run)
    return calls, answer


def _invoke(*args):
    return CliRunner().invoke(cli.main, list(args))


def test_license_runs_the_check_in_the_api_container(backend):
    calls, _ = backend
    result = _invoke("license")
    assert result.exit_code == 2, result.output
    assert "holds no license" in result.output
    cmd = calls[0]
    assert cmd[:7] == [
        "docker",
        "exec",
        stack.API_CONTAINER,
        "python",
        "manage.py",
        "shell",
        "-c",
    ]
    assert "VALIDATE = True" in cmd[7] and "SYNC = False" in cmd[7]


def test_offline_does_not_ask_the_service(backend):
    calls, _ = backend
    _invoke("license", "--offline")
    assert "VALIDATE = False" in calls[0][7]


def test_sync_runs_the_backends_task(backend):
    calls, _ = backend
    _invoke("license", "sync")
    assert "SYNC = True" in calls[0][7]


def test_json_is_the_report_and_the_findings(backend):
    result = _invoke("license", "--json")
    body = json.loads(result.output)
    assert body["report"]["mint_email"] == EMAIL
    assert body["findings"][0]["level"] == "fail"


def test_a_stopped_backend_says_to_start_it(monkeypatch):
    monkeypatch.setattr(stack, "ensure_docker", lambda: "2.29")
    monkeypatch.setattr(lic, "_container_running", lambda name: False)
    result = _invoke("license")
    assert result.exit_code == 1
    assert "arcsecond start" in result.output
