"""`arcsecond license`: what this installation's license really is, and why.

Three places answer "is this installation licensed?" and they can disagree:
the boot log (the License rows the backend holds for its installation), the
Settings panel (which, until November 2026, read "Activated" from the
owner's verified address alone), and Keygen (behind licensing.arcsecond.io).
A box whose mint the licensing service keeps refusing shows all three at
once: "No license found" at boot, "Activated" in the browser, and at Keygen a
license that exists but that nothing has validated in 90 days.

So this does not re-implement anything. It runs a short script inside the
running backend container, with the backend's own code: the same
`Installation.objects.local()`, the same `has_valid_license()`, the same
`LicenseServiceClient.validate_license()` the nightly sync calls, with this
machine's fingerprint. What it prints is what the backend sees, plus a
sentence for each thing that is wrong.

`arcsecond license sync` runs the backend's sync task itself, here and now
rather than on a worker: re-validate every license, and try the mint the boot
and the nightly beat try. The licensing service's answer to that mint, which
otherwise only reaches the worker's log, is printed.

Nothing here reads or prints the license key or the full fingerprint.
"""

import json
import subprocess

import click

from arcsecond.errors import ArcsecondError
from arcsecond.options import basic_options

from . import stack
from .utils import _container_running

API_CONTAINER = stack.API_CONTAINER
WORKER_CONTAINER = "arcsecond-worker"
MARK = "@@ARCSECOND-LICENSE@@"

# The service retries a call that got no answer twice, 10 s then 30 s apart
# (installation/services/licenses/service_client.py), per license.
PROBE_TIMEOUT = 300

OK, INFO, WARN, FAIL = "ok", "info", "warn", "fail"

# Run with `manage.py shell -c`. Every
# step is guarded on its own, so an older image that lacks one function still
# reports the rest. Ends with one marked line of JSON: Django may print things
# of its own before it.
PROBE = r"""
import json, logging
MARK = '@@ARCSECOND-LICENSE@@'
VALIDATE = __VALIDATE__
SYNC = __SYNC__
report = {'errors': []}
records = []

class _Capture(logging.Handler):
    def emit(self, record):
        try:
            records.append({'level': record.levelname, 'logger': record.name, 'message': record.getMessage()})
        except Exception:
            pass

# What the licensing client logs is the licensing service's answer, and the
# point of `sync`: this one process hears it whatever the settings silenced.
logging.disable(logging.NOTSET)
_logger = logging.getLogger('arcsecond.installation')
_logger.addHandler(_Capture(level=logging.INFO))
_logger.setLevel(logging.INFO)

def _try(label, fn, default=None):
    try:
        return fn()
    except Exception as e:
        report['errors'].append('%s: %s: %s' % (label, type(e).__name__, e))
        return default

def _iso(d):
    return d.isoformat() if d else None

def _mask(v):
    return '%s... (%d chars)' % (v[:8], len(v)) if v else ''

try:
    from django.conf import settings
    from arcsecond.installation.models import Installation, License

    report['service_url'] = getattr(settings, 'ARCSECOND_LICENSE_SERVICE_URL', '') or 'https://licensing.arcsecond.io'
    local = Installation.objects.local()

    def _installations():
        return [{
            'id': i.pk, 'mode': i.mode, 'created': _iso(i.creation_date),
            'fingerprint': _mask(i.machine_fingerprint),
            'is_local': local is not None and i.pk == local.pk,
        } for i in Installation.objects.order_by('creation_date')]

    def _licenses():
        return [{
            'id': l.pk, 'installation': l.installation_id, 'email': l.email, 'is_trial': l.is_trial,
            'status': l.keygen_license_status, 'expiry': _iso(l.expiry_date),
            'keygen_license_id': l.keygen_license_id, 'has_key': bool(l.keygen_license_key),
            'is_valid': l.is_valid, 'created': _iso(l.creation_date),
        } for l in License.objects.order_by('creation_date')]

    report['installations'] = _try('installations', _installations, [])
    report['licenses'] = _try('licenses', _licenses, [])

    if local is not None:
        report['local'] = {
            'id': local.pk,
            'has_fingerprint': bool(local.machine_fingerprint),
            'has_valid_license': _try('has_valid_license', local.has_valid_license),
            'email_verification_pending': _try('is_email_verification_pending', local.is_email_verification_pending),
            'setup_blocked': _try('is_setup_blocked', local.is_setup_blocked),
            'verification_deadline': _iso(getattr(local, 'verification_deadline', None)),
        }

        def _owners():
            from allauth.account.models import EmailAddress
            from arcsecond.installation.utils import local_installation_admin_users
            users = local_installation_admin_users(owners_only=True)
            return [{'username': a.user.username, 'email': a.email, 'primary': a.primary, 'verified': a.verified}
                    for a in EmailAddress.objects.filter(user__in=users).select_related('user')
                    .order_by('user_id', '-primary')]
        report['owner_addresses'] = _try('owner addresses', _owners, [])

        def _mint_email():
            from arcsecond.installation.services.licenses.auto_mint import find_admin_primary_email
            return find_admin_primary_email()
        report['mint_email'] = _try('mint address', _mint_email)

        if VALIDATE:
            from arcsecond.installation.services.licenses import LicenseServiceClient
            validations = []
            for lic in License.objects.order_by('creation_date'):
                if not lic.keygen_license_key:
                    continue
                def _validate(lic=lic):
                    client = LicenseServiceClient(lic.email, local.machine_fingerprint, lic.is_trial)
                    r = client.validate_license(lic.keygen_license_key)
                    return {'license': lic.pk, 'valid': bool(r.get('valid')), 'status': r.get('status', ''),
                            'code': r.get('code', ''), 'cause': r.get('cause', ''), 'expiry': _iso(r.get('expiry'))}
                validations.append(_try('validate license %s' % lic.pk, _validate,
                                        {'license': lic.pk, 'valid': False, 'code': 'error'}))
            report['validations'] = validations

        if SYNC:
            def _sync():
                from arcsecond.installation.tasks import sync_license_statuses_with_keygen
                sync_license_statuses_with_keygen()
                return True
            report['synced'] = _try('sync', _sync, False)
            report['licenses_after'] = _try('licenses', _licenses, [])
            local.refresh_from_db()
            report['local']['has_valid_license_after'] = _try('has_valid_license', local.has_valid_license)
except Exception as e:
    report['errors'].append('fatal: %s: %s' % (type(e).__name__, e))

report['log'] = records
print(MARK + json.dumps(report))
"""


def build_probe(validate: bool, sync: bool) -> str:
    return PROBE.replace("__VALIDATE__", repr(bool(validate))).replace(
        "__SYNC__", repr(bool(sync))
    )


def parse_probe_output(stdout: str) -> dict:
    for line in reversed((stdout or "").splitlines()):
        if line.startswith(MARK):
            try:
                return json.loads(line[len(MARK) :])
            except ValueError:
                break
    raise ArcsecondError(
        "The backend ran the license check but gave no readable answer. "
        "Its output was:\n" + (stdout or "").strip()[-2000:]
    )


def run_probe(validate: bool = True, sync: bool = False) -> dict:
    """Run the probe in the backend container and return its report."""
    stack.ensure_docker()
    if not _container_running(API_CONTAINER):
        raise ArcsecondError(
            f"The {API_CONTAINER} container is not running, and the license lives in "
            "its database. Start Arcsecond.local first:  arcsecond start"
        )
    try:
        # `-c`, not the script on stdin: `shell` only reads stdin when it is
        # readable the instant it looks (a zero-timeout select), which over
        # `docker exec -i` is a race it can lose and fall into the REPL. The
        # script carries no secret, so argv is fine.
        result = subprocess.run(
            [
                "docker",
                "exec",
                API_CONTAINER,
                "python",
                "manage.py",
                "shell",
                "-c",
                build_probe(validate, sync),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=PROBE_TIMEOUT,
        )
    except FileNotFoundError:
        raise ArcsecondError(stack.DOCKER_NOT_INSTALLED) from None
    except subprocess.TimeoutExpired:
        raise ArcsecondError(
            f"The license check did not finish within {PROBE_TIMEOUT} s. The licensing "
            "service is probably not answering; `arcsecond doctor` checks the way out."
        ) from None
    if result.returncode != 0 and MARK not in (result.stdout or ""):
        detail = (result.stderr or result.stdout or "").strip()[-2000:]
        raise ArcsecondError(f"The backend could not run the license check:\n{detail}")
    return parse_probe_output(result.stdout)


# ---------------------------------------------------------------------------
# Reading the report
# ---------------------------------------------------------------------------

# Keygen's validation codes, as the licensing service passes them through.
_CODE_MEANINGS = {
    "VALID": None,
    "FINGERPRINT_SCOPE_MISMATCH": "it is bound to another machine, not to this one",
    "NO_MACHINE": "it is bound to no machine at all",
    "NO_MACHINES": "it is bound to no machine at all",
    "EXPIRED": "it has expired",
    "SUSPENDED": "it is suspended",
    "BANNED": "it is banned",
    "NOT_FOUND": "the licensing service does not know this key",
    "TOO_MANY_MACHINES": "it is bound to more machines than it allows",
}
_REBIND_CODES = {"FINGERPRINT_SCOPE_MISMATCH", "NO_MACHINE", "NO_MACHINES"}

REVERIFY_HINT = (
    "Prove the owner address from this machine: Headquarters > Observatory Settings > "
    "License Activation > Request the license again, and enter the code it mails. "
    "The licensing service then moves the license here. (If the panel says Activated "
    "and offers no such button, this Arcsecond.local predates the fix: "
    "`arcsecond update` first.)"
)


def _mint_refusal(log: list) -> list:
    """What the licensing service said to the mint the sync just tried."""
    findings = []
    for record in log or []:
        message = record.get("message", "")
        if "License mint failed" in message or "License mint request failed" in message:
            lowered = message.lower()
            if "another installation" in lowered:
                text = (
                    "The licensing service refuses to issue the license here: the address's "
                    "license is held by another installation, and the address was last "
                    "proven from that one. " + REVERIFY_HINT
                )
            elif "not been verified" in lowered:
                text = (
                    "The licensing service refuses to issue the license: it has never seen "
                    "the owner address verified (verified on this box only, before the "
                    "service did the verifying). " + REVERIFY_HINT
                )
            elif "http 409" in lowered:
                text = (
                    "The licensing service refuses: the address is registered in another "
                    "licensing environment. Nothing to fix on this machine; write to "
                    "team@arcsecond.io."
                )
            elif "request failed" in message:
                text = (
                    "The licensing service could not be reached to issue the license. "
                    "`arcsecond doctor` checks the way out to licensing.arcsecond.io."
                )
            else:
                text = "The licensing service refused to issue the license."
            findings.append((FAIL, f"{text}\n  Its answer: {message}"))
    return findings


def _records(report: dict, local_id) -> list:
    """Several installation records, and licenses attached to the wrong one."""
    findings = []
    installations = report.get("installations") or []
    if len(installations) > 1:
        findings.append(
            (
                WARN,
                f"{len(installations)} installation records exist; the backend uses "
                f"#{local_id}, the oldest. Licenses attached to the others are ignored.",
            )
        )
    for lic in report.get("licenses") or []:
        if lic.get("installation") != local_id:
            findings.append(
                (
                    WARN,
                    f"License #{lic['id']} ({lic.get('email') or 'no address'}) belongs to "
                    f"installation #{lic.get('installation')}, not to #{local_id}. "
                    "The Settings panel lists it; the backend does not count it.",
                )
            )
    return findings


def _held(report: dict, local: dict) -> list:
    """What the licenses this installation holds amount to."""
    mine = [
        lic
        for lic in report.get("licenses") or []
        if lic.get("installation") == local.get("id")
    ]
    mint_email = report.get("mint_email")
    if not mine and mint_email:
        return [
            (
                FAIL,
                f"The owner address {mint_email} is verified, but this installation "
                'holds no license. That is why the boot log says "No license found" '
                "while the Settings panel says Activated: the panel read the verified "
                "address alone. At every boot and every night the backend asks the "
                "licensing service to issue the license, and it has been refused or "
                "unanswered. `arcsecond license sync` makes that request now and "
                "shows the answer.",
            )
        ]
    if not mine:
        return [
            (
                FAIL,
                "No license, and no verified owner address to issue one against. "
                "Finish activation in Headquarters > Observatory Settings > License "
                "Activation.",
            )
        ]
    if local.get("has_valid_license"):
        live = [lic for lic in mine if lic.get("is_valid")]
        lic = live[0] if live else mine[0]
        expiry = (lic.get("expiry") or "")[:10]
        return [
            (
                OK,
                f"License #{lic['id']} for {lic.get('email')}: {lic.get('status') or '?'}"
                + (f", expires {expiry}" if expiry else ", no expiry")
                + ".",
            )
        ]
    findings = []
    for lic in mine:
        expiry = (lic.get("expiry") or "")[:10]
        findings.append(
            (
                FAIL,
                f"License #{lic['id']} for {lic.get('email')} is not valid here: "
                f"status {lic.get('status') or 'unknown'}"
                + (f", expiry {expiry}" if expiry else "")
                + ".",
            )
        )
    return findings


def _verdict(v: dict) -> tuple:
    """The licensing service's answer about one license, for this machine."""
    label = f"License #{v.get('license')}"
    code = (v.get("code") or "").upper()
    if v.get("valid"):
        return (OK, f"{label}: the licensing service validates it on this machine.")
    if code == "UNREACHABLE":
        return (
            WARN,
            f"{label}: the licensing service gave no verdict "
            f"({v.get('cause') or 'no answer'}). `arcsecond doctor` checks the way out.",
        )
    meaning = _CODE_MEANINGS.get(code) or f"Keygen answered {code or 'not valid'}"
    text = f"{label}: the licensing service says it is not valid here: {meaning}."
    if code in _REBIND_CODES:
        text += " " + REVERIFY_HINT
    return (FAIL, text)


def _validations(report: dict) -> list:
    findings = []
    licenses = report.get("licenses") or []
    validations = report.get("validations") or []
    by_id = {lic["id"]: lic for lic in licenses}
    for v in validations:
        findings.append(_verdict(v))
        remote = (v.get("status") or "").upper()
        held = (by_id.get(v.get("license"), {}).get("status") or "").upper()
        if remote and held and remote != held:
            findings.append(
                (
                    INFO,
                    f"License #{v.get('license')}: Keygen says {remote}, this installation "
                    f"still records {held}. `arcsecond license sync` brings the record up "
                    "to date.",
                )
            )
    statuses = [(row.get("status") or "").upper() for row in [*licenses, *validations]]
    if "INACTIVE" in statuses:
        findings.append(
            (
                INFO,
                "INACTIVE at Keygen means nothing has validated the license in 90 days. "
                "It still counts as valid, but it says this installation has not been "
                "checking it.",
            )
        )
    return findings


def _backend_log(report: dict, local: dict) -> list:
    if "synced" not in report:
        return [
            (WARN, f"Backend: {record.get('message')}")
            for record in report.get("log") or []
            if record.get("level") in ("WARNING", "ERROR")
        ]
    findings = _mint_refusal(report.get("log"))
    if local.get("has_valid_license_after") and not local.get("has_valid_license"):
        findings.append(
            (OK, "The sync issued or revived the license: it is valid now.")
        )
    return findings


def diagnose(report: dict, worker_running=None) -> list:
    """(level, sentence) for everything worth saying, most important first."""
    findings = [
        (WARN, f"Part of the check could not run: {error}")
        for error in report.get("errors") or []
    ]
    local = report.get("local")
    if not local:
        findings.append(
            (
                FAIL,
                "There is no local installation record yet: the backend has not "
                "finished its first boot. `arcsecond logs backend` shows where it is.",
            )
        )
        return findings

    findings.extend(_records(report, local.get("id")))
    if local.get("setup_blocked"):
        findings.append(
            (
                FAIL,
                "The installation is blocked: its activation deadline has passed with "
                "no verified owner address and no valid license.",
            )
        )
    findings.extend(_held(report, local))
    findings.extend(_validations(report))
    findings.extend(_backend_log(report, local))
    if worker_running is False:
        findings.append(
            (
                WARN,
                f"The {WORKER_CONTAINER} container is not running. The boot-time and "
                "nightly license sync run there, so neither has been happening.",
            )
        )
    return findings


_SYMBOLS = {
    OK: ("✓", "green"),
    INFO: ("•", None),
    WARN: ("!", "yellow"),
    FAIL: ("✗", "red"),
}


def render(report: dict, findings: list) -> None:
    local = report.get("local") or {}
    owners = report.get("owner_addresses") or []
    click.echo(click.style("Arcsecond.local license", bold=True))
    click.echo(f"  Licensing service   {report.get('service_url', '?')}")
    for inst in report.get("installations") or []:
        marker = " (this one)" if inst.get("is_local") else ""
        click.echo(
            f"  Installation #{inst['id']}{marker}  {inst.get('mode')}, fingerprint "
            f"{inst.get('fingerprint') or 'none'}"
        )
    if owners:
        for addr in owners:
            state = "verified" if addr.get("verified") else "NOT verified"
            primary = "primary" if addr.get("primary") else "secondary"
            click.echo(
                f"  Owner {addr.get('username')}: {addr.get('email')} ({primary}, {state})"
            )
    elif local:
        click.echo("  Owner address       none")
    licenses = report.get("licenses_after") or report.get("licenses") or []
    if not licenses:
        click.echo("  Licenses            none")
    for lic in licenses:
        kind = "trial" if lic.get("is_trial") else "full"
        expiry = (lic.get("expiry") or "")[:10] or "no expiry"
        click.echo(
            f"  License #{lic['id']}  {lic.get('email')}, {kind}, "
            f"{lic.get('status') or 'no status'}, {expiry}, installation #{lic.get('installation')}"
        )
    click.echo("")
    for level, text in findings:
        symbol, colour = _SYMBOLS[level]
        click.echo(click.style(symbol, fg=colour, bold=True) + " " + text)


def exit_code(findings: list) -> int:
    levels = {level for level, _ in findings}
    if FAIL in levels:
        return 2
    if WARN in levels:
        return 1
    return 0


def _report(validate: bool, sync: bool, as_json: bool) -> None:
    report = run_probe(validate=validate, sync=sync)
    findings = diagnose(report, worker_running=_container_running(WORKER_CONTAINER))
    if as_json:
        click.echo(
            json.dumps(
                {
                    "report": report,
                    "findings": [{"level": lvl, "text": txt} for lvl, txt in findings],
                },
                indent=2,
            )
        )
    else:
        render(report, findings)
    raise SystemExit(exit_code(findings))


json_option = click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print the whole report as JSON, for a support conversation.",
)


@click.group(
    name="license",
    invoke_without_command=True,
    short_help="Is this installation licensed, and if not, why not.",
)
@click.option(
    "--offline",
    is_flag=True,
    help="Read what the installation holds without asking the licensing service.",
)
@json_option
@click.pass_context
def license_group(ctx, offline, as_json):
    """Is this installation licensed, and if not, why not.

    Checks the license the way the backend does, with the backend's own code,
    inside the running container: which license it holds, whether the owner
    address is verified, and what the licensing service says about each license
    for this machine. Nothing is changed.

    \b
      arcsecond license          check, and ask the licensing service
      arcsecond license sync     run the backend's license sync now, and show its answer

    Exit code: 0 when the license is valid, 1 on a warning, 2 when it is not.
    """
    if ctx.invoked_subcommand is None:
        if not as_json:
            click.echo(
                "Asking the backend"
                + ("" if offline else " and the licensing service")
                + "..."
            )
        _report(validate=not offline, sync=False, as_json=as_json)


@license_group.command(
    name="sync", short_help="Run the backend's license sync now, and show its answer."
)
@json_option
@basic_options
def license_sync(as_json):
    """Run the backend's license sync now, here rather than on the worker.

    The same task the boot and the nightly beat queue: re-validate every
    license and update its status and expiry, then, if the verified owner
    address still has no license, ask the licensing service to issue it. What
    the service answers is printed, instead of only reaching the worker's log.
    """
    if not as_json:
        click.echo(
            "Running the backend's license sync (up to a minute when the service is slow)..."
        )
    _report(validate=True, sync=True, as_json=as_json)
