"""Tests for sensor/profile observation integration in the data collector."""

from types import SimpleNamespace

import pytest

from backend.src.config.settings import settings
from backend.src.services.data_collector import DataCollector
from backend.src.utils.logger import logger


PROFILE = {
    "temp_min": 20.0,
    "temp_max": 30.0,
    "humidity_min": 40.0,
    "humidity_max": 80.0,
}
READINGS = {
    "bme280": {"status": "ok", "temperature": 24.0, "humidity": 50.0},
    "bme680": {"status": "ok", "temperature": 26.0, "humidity": 70.0},
}


@pytest.mark.asyncio
async def test_configured_profile_observation_logs_values_without_gpio(monkeypatch):
    monkeypatch.setattr(settings, "actuator_profile_user_id", 17)
    collector = DataCollector()
    collector._config_cache = {17: SimpleNamespace(**PROFILE)}
    messages = []
    monkeypatch.setattr(logger, "info", messages.append)

    await collector._observe_actuator_control(READINGS)

    assert len(messages) == 1
    assert "temperature=25.00°C (range 20.00-30.00°C)" in messages[0]
    assert "humidity=60.00% (range 40.00-80.00%)" in messages[0]
    assert "GPIO disabled" in messages[0]
    assert collector.get_status()["actuator_control"]["gpio_enabled"] is False


@pytest.mark.asyncio
async def test_observation_is_disabled_without_a_configured_user(monkeypatch):
    monkeypatch.setattr(settings, "actuator_profile_user_id", None)
    collector = DataCollector()
    messages = []
    monkeypatch.setattr(logger, "info", messages.append)

    await collector._observe_actuator_control(READINGS)

    assert messages == []
    status = collector.get_status()["actuator_control"]
    assert status == {
        "mode": "disabled",
        "profile_user_id": None,
        "gpio_enabled": False,
    }
