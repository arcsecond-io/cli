"""The installation's own Tomorrow.io key: asked while empty, never shipped."""

from types import SimpleNamespace

import pytest

from arcsecond.hosting import doctor, forecast


@pytest.fixture
def env(tmp_path):
    path = tmp_path / ".env"
    path.write_text(f"{forecast.ENV_COMMENT}\nTOMORROW_IO_API_KEY=\n", encoding="utf-8")
    return path


def _key(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("TOMORROW_IO_API_KEY="):
            return line.split("=", 1)[1]
    return None


def test_the_flag_records_the_key_without_asking(env, monkeypatch):
    monkeypatch.setattr(forecast.click, "prompt", lambda *a, **k: pytest.fail("asked"))
    forecast.offer(env, key=" abc123 ", interactive=True)
    assert _key(env) == "abc123"
    assert env.read_text().count("TOMORROW_IO_API_KEY=") == 1


def test_an_empty_flag_removes_the_key(env):
    forecast.offer(env, key="abc123")
    forecast.offer(env, key="")
    assert _key(env) == ""


def test_an_empty_key_is_asked_for_and_an_answer_recorded(env, monkeypatch):
    monkeypatch.setattr(forecast.click, "prompt", lambda *a, **k: "abc123")
    forecast.offer(env, interactive=True)
    assert _key(env) == "abc123"


def test_an_empty_answer_leaves_it_empty_and_the_next_setup_asks_again(
    env, monkeypatch
):
    asked = []
    monkeypatch.setattr(forecast.click, "prompt", lambda *a, **k: asked.append(1) or "")
    forecast.offer(env, interactive=True)
    forecast.offer(env, interactive=True)
    assert _key(env) == ""
    assert len(asked) == 2


def test_a_recorded_key_is_not_asked_for_again(env, monkeypatch):
    forecast.offer(env, key="abc123")
    monkeypatch.setattr(
        forecast.click, "prompt", lambda *a, **k: pytest.fail("asked again")
    )
    forecast.offer(env, interactive=True)


def test_without_a_terminal_nothing_is_asked(env, monkeypatch):
    monkeypatch.setattr(forecast.click, "prompt", lambda *a, **k: pytest.fail("asked"))
    forecast.offer(env, interactive=False)
    assert _key(env) == ""


def test_the_next_step_line_only_while_there_is_no_key(env):
    assert "--tomorrow-io-key" in forecast.next_step(env)
    forecast.offer(env, key="abc123")
    assert forecast.next_step(env) is None


def test_doctor_warns_without_a_key_and_says_how():
    finding = doctor.check_forecast_key(SimpleNamespace(read_env=lambda k: ""))
    assert finding.status == doctor.WARN
    assert "--tomorrow-io-key" in finding.fix


def test_doctor_is_content_with_a_key():
    finding = doctor.check_forecast_key(SimpleNamespace(read_env=lambda k: "abc123"))
    assert finding.status == doctor.OK
