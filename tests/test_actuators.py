"""Tests for authenticated shared-Pi actuator API and fail-off behavior."""

import asyncio
import sys
import types
from datetime import time

import pytest
from fastapi.testclient import TestClient

from backend.src.config.settings import settings
from backend.src.main import app
from backend.src.services.actuator_manager import ACTUATOR_PINS, actuator_manager
from backend.src.storage import db_manager


PASSWORD = "correct-horse-9"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_manager.db_path = str(tmp_path / "actuator-test.db")
    asyncio.run(db_manager.initialize())
    monkeypatch.setattr(settings, "actuator_hardware_enabled", False)
    monkeypatch.setattr(settings, "use_mock_sensors", False)
    actuator_manager._devices.clear()
    actuator_manager._automatic_user_id = None
    return TestClient(app)


def auth_headers(client):
    registered = client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": "actuator@example.com", "password": PASSWORD},
    )
    assert registered.status_code == 201
    response = client.post(
        "/api/auth/login",
        json={"email": "actuator@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_actuator_state_requires_sign_in(client):
    assert client.get("/api/actuators/").status_code == 401


def test_physical_outputs_are_disabled_by_default(client):
    headers = auth_headers(client)

    response = client.get("/api/actuators/", headers=headers)
    assert response.status_code == 200
    state = response.json()
    assert state["hardware_enabled"] is False
    assert state["automatic_available"] is False
    assert state["fan_on"] is False
    assert state["humidifier_on"] is False
    assert state["grow_light_on"] is False

    response = client.post(
        "/api/actuators/fan/state", json={"on": True}, headers=headers
    )
    assert response.status_code == 409


def test_auto_mode_requires_hardware_to_be_enabled(client):
    headers = auth_headers(client)
    response = client.post("/api/actuators/automatic?enabled=true", headers=headers)

    assert response.status_code == 409
    assert "ACTUATOR_HARDWARE_ENABLED=True" in response.json()["detail"]


def test_automatic_control_uses_profile_band_hysteresis(client, monkeypatch):
    class FakeOutputDevice:
        def __init__(self, pin, active_high, initial_value):
            self.pin = pin
            self.is_active = initial_value

        def on(self):
            self.is_active = True

        def off(self):
            self.is_active = False

        def close(self):
            self.off()

    monkeypatch.setitem(
        sys.modules,
        "gpiozero",
        types.SimpleNamespace(OutputDevice=FakeOutputDevice),
    )
    monkeypatch.setattr(settings, "actuator_hardware_enabled", True)
    monkeypatch.setattr(
        "backend.src.services.actuator_manager.AUTOMATIC_MIN_SWITCH_INTERVAL_SECONDS",
        0,
    )
    headers = auth_headers(client)
    response = client.post("/api/actuators/automatic?enabled=true", headers=headers)
    assert response.status_code == 200
    assert response.json()["automatic_enabled"] is True

    profile = asyncio.run(
        db_manager.get_active_configuration(actuator_manager._automatic_user_id)
    )
    temperature = profile["temp_max"] + 1
    humidity = profile["humidity_min"] - 1
    readings = {
        "bme280": {"status": "ok", "temperature": temperature, "humidity": humidity},
        "bme680": {"status": "ok", "temperature": temperature, "humidity": humidity},
    }
    asyncio.run(actuator_manager.evaluate_automatic(readings))
    state = asyncio.run(actuator_manager.get_state())
    assert state["fan_on"] is True
    assert state["humidifier_on"] is True

    within_bands = {
        "bme280": {
            "status": "ok",
            "temperature": (profile["temp_min"] + profile["temp_max"]) / 2,
            "humidity": (profile["humidity_min"] + profile["humidity_max"]) / 2,
        },
        "bme680": {
            "status": "ok",
            "temperature": (profile["temp_min"] + profile["temp_max"]) / 2,
            "humidity": (profile["humidity_min"] + profile["humidity_max"]) / 2,
        },
    }
    asyncio.run(actuator_manager.evaluate_automatic(within_bands))
    state = asyncio.run(actuator_manager.get_state())
    assert state["fan_on"] is True
    assert state["humidifier_on"] is True

    asyncio.run(actuator_manager.evaluate_automatic({}))
    state = asyncio.run(actuator_manager.get_state())
    assert state["fan_on"] is False
    assert state["humidifier_on"] is False

    response = client.post(
        "/api/actuators/automatic?enabled=false", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["automatic_enabled"] is False


def test_light_schedule_cannot_be_enabled_when_hardware_is_disabled(client):
    headers = auth_headers(client)
    response = client.put(
        "/api/actuators/light-schedule",
        json={"enabled": True, "start": "06:00", "end": "22:00"},
        headers=headers,
    )

    assert response.status_code == 409


def test_schedule_times_can_be_saved_while_disabled(client):
    headers = auth_headers(client)
    response = client.put(
        "/api/actuators/light-schedule",
        json={"enabled": False, "start": "06:30", "end": "21:15"},
        headers=headers,
    )

    assert response.status_code == 200
    state = response.json()
    assert state["light_schedule_enabled"] is False
    assert state["light_start"] == "06:30"
    assert state["light_end"] == "21:15"


def test_light_schedule_validates_times(client):
    headers = auth_headers(client)
    response = client.put(
        "/api/actuators/light-schedule",
        json={"enabled": False, "start": "25:00", "end": "22:00"},
        headers=headers,
    )
    assert response.status_code == 422

    response = client.put(
        "/api/actuators/light-schedule",
        json={"enabled": True, "start": "06:00", "end": "06:00"},
        headers=headers,
    )
    assert response.status_code == 422


def test_manual_output_controls_use_active_low_mapped_gpio(client, monkeypatch):
    class FakeOutputDevice:
        def __init__(self, pin, active_high, initial_value):
            self.pin = pin
            self.active_high = active_high
            self.is_active = initial_value

        def on(self):
            self.is_active = True

        def off(self):
            self.is_active = False

        def close(self):
            self.off()

    monkeypatch.setitem(
        sys.modules,
        "gpiozero",
        types.SimpleNamespace(OutputDevice=FakeOutputDevice),
    )
    monkeypatch.setattr(settings, "actuator_hardware_enabled", True)
    headers = auth_headers(client)
    response = client.post(
        "/api/actuators/fan/state", json={"on": True}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["fan_on"] is True
    assert set(ACTUATOR_PINS.values()) == {12, 16, 21}
    assert all(device.active_high is False for device in actuator_manager._devices.values())

    response = client.post(
        "/api/actuators/fan/state", json={"on": False}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["fan_on"] is False


def test_grow_light_schedule_handles_daily_and_overnight_intervals():
    is_on = actuator_manager._schedule_is_on
    assert is_on(time(12, 0), "06:00", "22:00")
    assert not is_on(time(23, 0), "06:00", "22:00")
    assert is_on(time(23, 0), "22:00", "06:00")
    assert is_on(time(5, 0), "22:00", "06:00")
    assert not is_on(time(12, 0), "22:00", "06:00")
