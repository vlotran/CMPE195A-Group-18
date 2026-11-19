# tests/test_auth.py
"""
Tests for login/logout and per-user threshold profiles.

Each test gets its own empty SQLite file, so tests never touch data/hydroponic.db
The app's background sensor loop is NOT started (TestClient is used without
`with`), so these run fast and need no hardware.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.src.main import app
from backend.src.storage import db_manager
from backend.src.services.data_collector import data_collector

PASSWORD = "correct-horse-9"


# FIXTURES / HELPERS 

@pytest.fixture
def client(tmp_path):
    """Fresh database + API client for every test."""
    db_manager.db_path = str(tmp_path / "test.db")
    asyncio.run(db_manager.initialize())
    data_collector.invalidate_config()
    data_collector.evaluators.clear()
    return TestClient(app)


def register(client, email="ana@example.com", name="Ana", password=PASSWORD):
    return client.post(
        "/api/auth/register", json={"name": name, "email": email, "password": password}
    )


def login(client, email="ana@example.com", password=PASSWORD):
    """Register + log in, return auth headers for that user."""
    register(client, email=email)
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def profile(name="My Lettuce"):
    return {
        "name": name, "ph_min": 5.5, "ph_max": 6.5, "temp_min": 18, "temp_max": 24,
        "humidity_min": 50, "humidity_max": 70,
    }


#  REGISTER / LOGIN / LOGOUT 

def test_register_creates_user_with_example_profiles(client):
    res = register(client)
    assert res.status_code == 201
    assert res.json() == {"id": 1, "name": "Ana", "email": "ana@example.com"}

    headers = login(client)
    profiles = client.get("/api/configurations/", headers=headers).json()
    names = {p["name"] for p in profiles}
    assert len(profiles) == 10  # every template copied
    assert {"Lettuce", "Tomato", "Standard Hydroponic Range"} <= names

    # exactly one starts active
    active = client.get("/api/configurations/active", headers=headers).json()
    assert active["name"] == "Standard Hydroponic Range"


def test_duplicate_email_is_rejected_case_insensitively(client):
    register(client, email="ana@example.com")
    res = register(client, email="ANA@Example.com")
    assert res.status_code == 409


def test_register_validates_input(client):
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, password="short").status_code == 422
    assert register(client, name="   ").status_code == 422


def test_password_is_not_stored_in_plain_text(client):
    register(client)
    user = asyncio.run(db_manager.get_user_by_email("ana@example.com"))
    assert PASSWORD not in user["password_hash"]
    assert user["password_hash"].startswith("scrypt$")


def test_wrong_password_and_unknown_email_get_the_same_error(client):
    register(client)
    wrong_pw = client.post(
        "/api/auth/login", json={"email": "ana@example.com", "password": "nope-nope-1"}
    )
    no_user = client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": PASSWORD}
    )
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_me_and_logout(client):
    headers = login(client)
    assert client.get("/api/auth/me", headers=headers).json()["name"] == "Ana"

    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    # the same token is dead immediately
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_expired_session_is_rejected(client):
    headers = login(client)

    async def expire_all():
        import aiosqlite
        async with aiosqlite.connect(db_manager.db_path) as db:
            await db.execute("UPDATE sessions SET expires_at = datetime('now', '-1 second')")
            await db.commit()

    asyncio.run(expire_all())
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_protected_routes_need_a_token(client):
    assert client.get("/api/configurations/").status_code == 401
    assert client.get("/api/alerts/").status_code == 401
    bad = {"Authorization": "Bearer made-up-token"}
    assert client.get("/api/configurations/", headers=bad).status_code == 401


def test_sensor_routes_stay_public(client):
    # one Pi, one garden: readings don't need a login
    assert client.get("/api/sensors/latest").status_code == 200
    assert client.get("/api/status").status_code == 200


# PER-USER PROFILES 

def test_profiles_are_private_to_each_user(client):
    ana = login(client, email="ana@example.com")
    bob = login(client, email="bob@example.com")

    created = client.post("/api/configurations/", json=profile(), headers=ana).json()["data"]
    pid = created["id"]

    # Bob can't see, edit, activate or delete Ana's profile: all look "not found"
    assert client.get(f"/api/configurations/{pid}", headers=bob).status_code == 404
    assert client.patch(f"/api/configurations/{pid}", json={"ph_min": 6}, headers=bob).status_code == 404
    assert client.post(f"/api/configurations/{pid}/activate", headers=bob).status_code == 404
    assert client.delete(f"/api/configurations/{pid}", headers=bob).status_code == 404
    assert "My Lettuce" not in {p["name"] for p in client.get("/api/configurations/", headers=bob).json()}


def test_deleting_example_profile_only_affects_that_user(client):
    ana = login(client, email="ana@example.com")
    bob = login(client, email="bob@example.com")

    tomato = next(p for p in client.get("/api/configurations/", headers=ana).json() if p["name"] == "Tomato")
    assert client.delete(f"/api/configurations/{tomato['id']}", headers=ana).status_code == 200

    ana_names = {p["name"] for p in client.get("/api/configurations/", headers=ana).json()}
    bob_names = {p["name"] for p in client.get("/api/configurations/", headers=bob).json()}
    assert "Tomato" not in ana_names
    assert "Tomato" in bob_names


def test_activating_only_changes_your_own_active_profile(client):
    ana = login(client, email="ana@example.com")
    bob = login(client, email="bob@example.com")

    basil = next(p for p in client.get("/api/configurations/", headers=ana).json() if p["name"] == "Basil")
    client.post(f"/api/configurations/{basil['id']}/activate", headers=ana)

    assert client.get("/api/configurations/active", headers=ana).json()["name"] == "Basil"
    assert client.get("/api/configurations/active", headers=bob).json()["name"] == "Standard Hydroponic Range"


def test_same_profile_name_allowed_for_different_users_but_not_twice(client):
    ana = login(client, email="ana@example.com")
    bob = login(client, email="bob@example.com")

    assert client.post("/api/configurations/", json=profile("Shared Name"), headers=ana).status_code == 201
    assert client.post("/api/configurations/", json=profile("Shared Name"), headers=bob).status_code == 201
    assert client.post("/api/configurations/", json=profile("Shared Name"), headers=ana).status_code == 409


def test_restart_does_not_duplicate_templates(client):
    asyncio.run(db_manager.initialize())  # simulate a second server start
    headers = login(client)
    assert len(client.get("/api/configurations/", headers=headers).json()) == 10


#  PER-USER ALERTS 

def test_alerts_follow_each_users_own_profile(client):
    ana = login(client, email="ana@example.com")
    bob = login(client, email="bob@example.com")

    # Ana: 20-25 C (Standard). Bob: widen to 0-50C so 40 C is normal for him.
    bob_active = client.get("/api/configurations/active", headers=bob).json()
    client.patch(f"/api/configurations/{bob_active['id']}", json={"temp_min": 0, "temp_max": 50}, headers=bob)

    # Feed a hot reading enough times to get past the evaluator's confirmation
    hot = {"bme280": {"status": "ok", "temperature": 40.0}}
    for _ in range(5):
        asyncio.run(data_collector._evaluate_alerts(hot))

    ana_alerts = client.get("/api/alerts/", headers=ana).json()
    bob_alerts = client.get("/api/alerts/", headers=bob).json()
    assert any(a["severity"] == "danger" for a in ana_alerts)
    assert bob_alerts == []

    # Bob can't mark Ana's alert as read
    assert client.patch(f"/api/alerts/{ana_alerts[0]['id']}/read", headers=bob).status_code == 404
    assert client.patch(f"/api/alerts/{ana_alerts[0]['id']}/read", headers=ana).status_code == 200

# DELETE ACCOUNT

def delete_me(client, headers, password=PASSWORD):
    """DELETE with a JSON body (TestClient.delete() can't send one)."""
    return client.request("DELETE", "/api/auth/me", headers=headers, json={"password": password})


def test_delete_account_removes_the_user_and_everything_they_own(client):
    ana = login(client, "ana@example.com")
    bob = login(client, "bob@example.com")
    ana_id = client.get("/api/auth/me", headers=ana).json()["id"]
    asyncio.run(db_manager.create_alert({
        "user_id": ana_id, "alert_type": "threshold_breach",
        "message": "x", "severity": "warning",
    }))

    res = delete_me(client, ana)
    assert res.status_code == 200

    # The token stops working right away
    assert client.get("/api/auth/me", headers=ana).status_code == 401

    # Nothing of Ana's is left behind
    import sqlite3
    with sqlite3.connect(db_manager.db_path) as db:
        for table in ("users", "sessions", "threshold_configurations", "alerts"):
            column = "id" if table == "users" else "user_id"
            left = db.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (ana_id,)).fetchone()[0]
            assert left == 0, table
        # Example profiles (templates) are shared and stay
        assert db.execute(
            "SELECT COUNT(*) FROM threshold_configurations WHERE user_id IS NULL"
        ).fetchone()[0] > 0

    # Other users are untouched
    assert client.get("/api/auth/me", headers=bob).status_code == 200
    assert client.get("/api/configurations/", headers=bob).json()


def test_deleted_email_can_sign_up_again(client):
    headers = login(client, "ana@example.com")
    delete_me(client, headers)
    assert register(client, "ana@example.com").status_code == 201


def test_delete_account_needs_login(client):
    assert client.request("DELETE", "/api/auth/me", json={"password": PASSWORD}).status_code == 401


def test_delete_account_with_wrong_password_keeps_everything(client):
    headers = login(client, "ana@example.com")

    res = delete_me(client, headers, password="wrong-password")

    # 403 (not 401) so the browser doesn't treat it as "logged out"
    assert res.status_code == 403
    assert res.json()["detail"] == "Incorrect password"
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.get("/api/configurations/", headers=headers).json()


def test_delete_account_needs_a_password(client):
    headers = login(client, "ana@example.com")
    assert client.request("DELETE", "/api/auth/me", headers=headers).status_code == 422
    assert client.get("/api/auth/me", headers=headers).status_code == 200
