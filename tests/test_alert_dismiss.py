# tests/test_alert_dismiss.py
"""""
Tests for deleting alerts from the alert panel (a "dismissed" flag, not a real delete)

Each test gets its own empty SQLite file, so tests never touch data/hydroponic.db
"""

import asyncio
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.src.main import app
from backend.src.storage import db_manager

PASSWORD = "correct-horse-9"


@pytest.fixture
def client(tmp_path):
    db_manager.db_path = str(tmp_path / "test.db")
    asyncio.run(db_manager.initialize())
    return TestClient(app)


def login(client, email):
    """Register + log in, return (auth headers, user id)."""
    client.post(
        "/api/auth/register", json={"name": "Test", "email": email, "password": PASSWORD}
    )
    res = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    body = res.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def add_alert(user_id, severity="warning"):
    return asyncio.run(
        db_manager.create_alert(
            {
                "user_id": user_id,
                "alert_type": "threshold_breach",
                "message": f"{severity} alert",
                "severity": severity,
            }
        )
    )


def ids(client, headers, **params):
    return {a["id"] for a in client.get("/api/alerts/", headers=headers, params=params).json()}


def test_dismiss_hides_one_alert_but_keeps_the_row(client):
    headers, user_id = login(client, "ana@example.com")
    first, second = add_alert(user_id), add_alert(user_id)

    assert client.patch(f"/api/alerts/{first}/dismiss", headers=headers).status_code == 200

    # Gone from the list and from the unread list that drives the badge and popup
    assert ids(client, headers) == {second}
    assert ids(client, headers, unread_only=True) == {second}

    # Still in the database as history
    with sqlite3.connect(db_manager.db_path) as db:
        row = db.execute("SELECT is_dismissed FROM alerts WHERE id = ?", (first,)).fetchone()
    assert row == (1,)


def test_cannot_dismiss_another_users_alert(client):
    ana, ana_id = login(client, "ana@example.com")
    bob, _ = login(client, "bob@example.com")
    alert = add_alert(ana_id)

    assert client.patch(f"/api/alerts/{alert}/dismiss", headers=bob).status_code == 404
    assert client.patch("/api/alerts/dismiss", headers=bob).json()["dismissed"] == 0
    assert ids(client, ana) == {alert}


def test_clear_all_only_touches_this_user(client):
    ana, ana_id = login(client, "ana@example.com")
    bob, bob_id = login(client, "bob@example.com")
    add_alert(ana_id, "danger")
    add_alert(ana_id, "normal")
    bobs = add_alert(bob_id)

    assert client.patch("/api/alerts/dismiss", headers=ana).json()["dismissed"] == 2
    assert ids(client, ana) == set()
    assert ids(client, bob) == {bobs}


def test_clear_all_respects_the_severity_filter(client):
    headers, user_id = login(client, "ana@example.com")
    add_alert(user_id, "danger")
    warning = add_alert(user_id, "warning")

    res = client.patch("/api/alerts/dismiss", headers=headers, params={"severity": "danger"})
    assert res.json()["dismissed"] == 1
    assert ids(client, headers) == {warning}


def test_clear_all_rejects_an_unknown_severity(client):
    headers, user_id = login(client, "ana@example.com")
    alert = add_alert(user_id)

    res = client.patch("/api/alerts/dismiss", headers=headers, params={"severity": "bogus"})
    assert res.status_code == 422
    assert ids(client, headers) == {alert}


def test_clear_all_skips_alerts_newer_than_the_loaded_list(client):
    headers, user_id = login(client, "ana@example.com")
    seen = add_alert(user_id, "warning")
    raised_after_load = add_alert(user_id, "danger")

    client.patch("/api/alerts/dismiss", headers=headers, params={"max_id": seen})
    assert ids(client, headers) == {raised_after_load}


def test_existing_database_gets_the_new_column(client):
    """An older DB (e.g. on the Pi) must be upgraded on startup, keeping its alerts"""
    headers, user_id = login(client, "ana@example.com")
    alert = add_alert(user_id)
    with sqlite3.connect(db_manager.db_path) as db:
        db.execute("ALTER TABLE alerts DROP COLUMN is_dismissed")

    asyncio.run(db_manager.initialize())

    assert ids(client, headers) == {alert}
