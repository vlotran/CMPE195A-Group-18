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


def record(user_id, state, monkeypatch):
    """Record one transition; return the emails it sent as (to, subject, body)."""
    sent = []

    async def fake_send(*args):
        sent.append(args)

    monkeypatch.setattr(settings, "smtp_username", "pi@gmail.com")
    monkeypatch.setattr(dc, "send_email", fake_send)
    collector = dc.DataCollector()

    async def run():
        await collector._record_alert(transition(state), user_id)
        if collector._email_tasks:
            await asyncio.gather(*collector._email_tasks)

    asyncio.run(run())
    return sent


def test_danger_alert_emails_the_profile_owner(client, monkeypatch):
    user_id = client.post("/api/auth/register", json=NEW_USER).json()["id"]

    sent = record(user_id, AlertState.DANGER, monkeypatch)

    assert len(sent) == 1
    to, subject, body = sent[0]
    assert to == NEW_USER["email"]
    assert "Temperature" in subject
    assert "40.0 °C" in body and "20.0-25.0°C" in body


@pytest.mark.parametrize("state", [AlertState.WARNING, AlertState.NORMAL])
def test_other_alerts_do_not_email(client, monkeypatch, state):
    user_id = client.post("/api/auth/register", json=NEW_USER).json()["id"]
    assert record(user_id, state, monkeypatch) == []


def test_alert_for_deleted_user_sends_nothing(client, monkeypatch):
    assert record(99999, AlertState.DANGER, monkeypatch) == []


def test_danger_alert_sends_nothing_when_email_is_off(client, monkeypatch):
    user_id = client.post("/api/auth/register", json=NEW_USER).json()["id"]
    monkeypatch.setattr(dc, "send_email", lambda *a: pytest.fail("must not send"))

    async def run():
        collector = dc.DataCollector()
        await collector._record_alert(transition(AlertState.DANGER), user_id)
        assert not collector._email_tasks

    asyncio.run(run())


def test_ph_email_does_not_repeat_the_sensor_name(client, monkeypatch):
    user_id = client.post("/api/auth/register", json=NEW_USER).json()["id"]
    sent = []

    async def fake_send(*args):
        sent.append(args)

    monkeypatch.setattr(dc, "send_email", fake_send)
    asyncio.run(dc.DataCollector()._email_danger_alert(
        transition(AlertState.DANGER, sensor_type="ph", metric="ph"), user_id
    ))
    assert sent[0][2].startswith("pH is DANGER")
