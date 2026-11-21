# tests/test_email.py
"""Sign-up domain check and DANGER alert emails. No real DNS or SMTP is used"""

import asyncio
from types import SimpleNamespace

import pytest
from email_validator import EmailUndeliverableError
from fastapi.testclient import TestClient

from backend.src.api.routes import auth as auth_routes
from backend.src.config.settings import settings
from backend.src.main import app
from backend.src.services import email_service
from backend.src.services import data_collector as dc
from backend.src.services.alert_evaluator import AlertState
from backend.src.storage import db_manager

NEW_USER = {"name": "Ana", "email": "ana@gmail.con", "password": "correct-horse-9"}

@pytest.fixture
def client(tmp_path):
    db_manager.db_path = str(tmp_path / "test.db")
    asyncio.run(db_manager.initialize())
    return TestClient(app)

def transition(to_state, sensor_type="bme280", metric="temperature"):
    return SimpleNamespace(
        sensor_type=sensor_type, metric=metric, value=40.0, to_state=to_state,
        threshold_min=20.0, threshold_max=25.0,
        should_notify=to_state == AlertState.DANGER,
    )

def test_signup_rejects_domain_that_cannot_receive_mail(client, monkeypatch):
    def reject(*args, **kwargs):
        raise EmailUndeliverableError("no such domain")

    monkeypatch.setattr(settings, "check_email_domain", True)
    monkeypatch.setattr(auth_routes, "validate_email", reject)

    res = client.post("/api/auth/register", json=NEW_USER)

    assert res.status_code == 422
    assert "can't receive mail" in res.json()["detail"]
    assert asyncio.run(db_manager.get_user_by_email(NEW_USER["email"])) is None


def test_signup_accepts_domain_that_can_receive_mail(client, monkeypatch):
    monkeypatch.setattr(settings, "check_email_domain", True)
    monkeypatch.setattr(auth_routes, "validate_email", lambda *a, **k: None)

    assert client.post("/api/auth/register", json=NEW_USER).status_code == 201


def test_existing_account_can_still_log_in_when_domain_check_is_on(client, monkeypatch):
    client.post("/api/auth/register", json=NEW_USER)  # check is off here

    monkeypatch.setattr(settings, "check_email_domain", True)
    monkeypatch.setattr(auth_routes, "validate_email", lambda *a, **k: pytest.fail("login must not do DNS"))

    res = client.post("/api/auth/login", json={"email": NEW_USER["email"], "password": NEW_USER["password"]})
    assert res.status_code == 200


def test_send_uses_tls_login_and_builds_the_message(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def starttls(self, context):
            calls.append(("starttls",))
        def login(self, user, password):
            calls.append(("login", user, password))
        def send_message(self, msg):
            calls.append(("send", msg["To"], msg["Subject"], msg.get_content()))

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_username", "pi@gmail.com")
    monkeypatch.setattr(settings, "smtp_password", "secret")

    assert asyncio.run(email_service.send_email("ana@gmail.com", "Hi", "Body")) is True
    assert [c[0] for c in calls] == ["connect", "starttls", "login", "send"]  # TLS before password
    assert calls[-1][1:3] == ("ana@gmail.com", "Hi")


@pytest.mark.parametrize("smtp_from, expected", [
    ("", "pi@gmail.com"),                     
    ("alerts@gmail.com", "alerts@gmail.com"),  # Brevo: separate sender
])
def test_from_address(monkeypatch, smtp_from, expected):
    sent = []

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def starttls(self, context): pass
        def login(self, user, password): pass
        def send_message(self, msg): sent.append(msg["From"])

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_username", "pi@gmail.com")
    monkeypatch.setattr(settings, "smtp_from", smtp_from)

    asyncio.run(email_service.send_email("a@b.com", "s", "b"))
    assert expected in sent[0]


def test_email_is_off_without_smtp_username(monkeypatch):
    monkeypatch.setattr(email_service, "_send", lambda *a: pytest.fail("must not send"))
    assert asyncio.run(email_service.send_email("a@b.com", "s", "b")) is False


def test_smtp_failure_does_not_raise(monkeypatch):
    def boom(*args):
        raise OSError("mail server down")

    monkeypatch.setattr(settings, "smtp_username", "pi@gmail.com")
    monkeypatch.setattr(email_service, "_send", boom)
    assert asyncio.run(email_service.send_email("a@b.com", "s", "b")) is False


def capture_emails(monkeypatch):
    """Replace send_email; returns the list it records (to, subject, text, html) into."""
    sent = []

    async def fake_send(*args):
        sent.append(args)

    monkeypatch.setattr(settings, "smtp_username", "pi@gmail.com")
    monkeypatch.setattr(dc, "send_email", fake_send)
    return sent


class FakeEvaluator:
    """Returns a prepared transition for chosen (sensor, metric) pairs."""

    def __init__(self, transitions):
        self.transitions = transitions

    def evaluate(self, sensor_type, metric, value, config):
        return self.transitions.get((sensor_type, metric))


def run_cycle(user_id, transitions, readings, monkeypatch):
    """Run one alert-evaluation cycle and wait for its emails."""
    collector = dc.DataCollector()

    async def configs():
        return {user_id: SimpleNamespace()}

    monkeypatch.setattr(collector, "_get_configs", configs)
    collector.evaluators[user_id] = FakeEvaluator(transitions)

    async def run():
        await collector._evaluate_alerts(readings)
        if collector._email_tasks:
            await asyncio.gather(*collector._email_tasks)

    asyncio.run(run())
    return collector


READINGS = {
    "bme280": {"status": "ok", "temperature": 40.0, "humidity": 50.0},
    "bme680": {"status": "ok", "temperature": 40.0, "humidity": 90.0},
}


def test_dangers_in_one_cycle_are_combined_into_one_email(client, monkeypatch):
    user_id = client.post("/api/auth/register", json=NEW_USER).json()["id"]
    sent = capture_emails(monkeypatch)
    hum = transition(AlertState.DANGER, sensor_type="bme680", metric="humidity")
    hum.value, hum.threshold_min, hum.threshold_max = 90.0, 50.0, 70.0

    run_cycle(user_id, {
        ("bme280", "temperature"): transition(AlertState.DANGER, "bme280"),
        ("bme680", "temperature"): transition(AlertState.DANGER, "bme680"),
        ("bme680", "humidity"): hum,
        ("bme280", "humidity"): transition(AlertState.WARNING, "bme280", "humidity"),
    }, READINGS, monkeypatch)

    assert len(sent) == 1                       # one email, not three
    to, subject, text, html = sent[0]
    assert to == NEW_USER["email"]
    assert subject == "DANGER range reached: Temperature, Humidity"
    assert text.startswith("DANGER range reached!")
    assert "  - BME280 Sensor: 40.0 °C (104.0 °F) (DANGER)" in text
    assert "  - BME680 Sensor: 40.0 °C (104.0 °F) (DANGER)" in text
    assert "Your range: 20.0-25.0°C / 68.0-77.0°F" in text
    assert "  - BME680 Sensor: 90.0% (DANGER)" in text
    assert "Your range: 50.0-70.0%" in text
    assert "BME280 Sensor: 50" not in text      # the WARNING is not in the email
    # Temperature is listed before Humidity, like the dashboard
    assert text.index("Temperature:") < text.index("Humidity:")
    assert "<h2" in html and "DANGER range reached!" in html


def test_each_user_gets_their_own_email(client, monkeypatch):
    ana = client.post("/api/auth/register", json=NEW_USER).json()["id"]
    bob = client.post("/api/auth/register", json={**NEW_USER, "email": "bob@gmail.com"}).json()["id"]
    sent = capture_emails(monkeypatch)
    collector = dc.DataCollector()

    async def configs():
        return {ana: SimpleNamespace(), bob: SimpleNamespace()}

    monkeypatch.setattr(collector, "_get_configs", configs)
    for uid in (ana, bob):
        collector.evaluators[uid] = FakeEvaluator({("bme280", "temperature"): transition(AlertState.DANGER)})

    async def run():
        await collector._evaluate_alerts(READINGS)
        await asyncio.gather(*collector._email_tasks)

    asyncio.run(run())
    assert sorted(e[0] for e in sent) == ["ana@gmail.con", "bob@gmail.com"]


@pytest.mark.parametrize("state", [AlertState.WARNING, AlertState.NORMAL])
def test_other_alerts_do_not_email(client, monkeypatch, state):
    user_id = client.post("/api/auth/register", json=NEW_USER).json()["id"]
    sent = capture_emails(monkeypatch)
    run_cycle(user_id, {("bme280", "temperature"): transition(state)}, READINGS, monkeypatch)
    assert sent == []


def test_alert_for_deleted_user_sends_nothing(client, monkeypatch):
    sent = capture_emails(monkeypatch)
    run_cycle(99999, {("bme280", "temperature"): transition(AlertState.DANGER)}, READINGS, monkeypatch)
    assert sent == []


def test_danger_alert_sends_nothing_when_email_is_off(client, monkeypatch):
    user_id = client.post("/api/auth/register", json=NEW_USER).json()["id"]
    monkeypatch.setattr(dc, "send_email", lambda *a: pytest.fail("must not send"))
    collector = run_cycle(user_id, {("bme280", "temperature"): transition(AlertState.DANGER)},
                          READINGS, monkeypatch)
    assert not collector._email_tasks


def test_ph_sensor_is_named_after_its_metric():
    ph = transition(AlertState.DANGER, sensor_type="ph", metric="ph")
    ph.value, ph.threshold_min, ph.threshold_max = 5.1, 5.5, 6.5
    _, text, _ = dc.build_danger_email([ph])
    assert "  - pH Sensor: 5.1 (DANGER)" in text


def test_view_here_button_only_with_a_dashboard_url():
    t = [transition(AlertState.DANGER)]

    _, text, html = dc.build_danger_email(t, "")
    assert "View here" not in text and "View here" not in html

    _, text, html = dc.build_danger_email(t, "https://garden.example/app?a=1&b=2")
    assert "View here: https://garden.example/app?a=1&b=2" in text
    # the link is escaped inside the HTML attribute
    assert 'href="https://garden.example/app?a=1&amp;b=2"' in html and ">View here</a>" in html


def test_send_includes_html_version(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def starttls(self, context): pass
        def login(self, user, password): pass
        def send_message(self, msg): sent.append(msg)

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_username", "pi@gmail.com")

    asyncio.run(email_service.send_email("a@b.com", "s", "plain", "<b>rich</b>"))
    msg = sent[0]
    assert msg.get_body(("plain",)).get_content().strip() == "plain"
    assert msg.get_body(("html",)).get_content().strip() == "<b>rich</b>"
