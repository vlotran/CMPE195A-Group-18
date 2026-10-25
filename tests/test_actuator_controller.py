"""Tests for hardware-independent environmental hysteresis rules."""

import pytest

from backend.src.services.actuator_controller import (
    apply_hysteresis,
    observe_environment,
)


PROFILE = {
    "temp_min": 20.0,
    "temp_max": 30.0,
    "humidity_min": 40.0,
    "humidity_max": 80.0,
}


def sensor_readings(
    bme280_temperature=24.0,
    bme680_temperature=26.0,
    bme280_humidity=50.0,
    bme680_humidity=70.0,
):
    return {
        "bme280": {
            "status": "ok",
            "temperature": bme280_temperature,
            "humidity": bme280_humidity,
        },
        "bme680": {
            "status": "ok",
            "temperature": bme680_temperature,
            "humidity": bme680_humidity,
        },
    }


def test_observation_averages_sensors_and_uses_profile_bands():
    observation = observe_environment(sensor_readings(), PROFILE)

    assert observation is not None
    assert observation.temperature_c == 25.0
    assert observation.humidity_pct == 60.0
    assert observation.temperature_min_c == 20.0
    assert observation.temperature_max_c == 30.0
    assert observation.humidity_min_pct == 40.0
    assert observation.humidity_max_pct == 80.0


@pytest.mark.parametrize(
    ("currently_on", "measurement", "expected"),
    [
        (False, 25.0, False),
        (True, 25.0, True),
        (False, 30.1, True),
        (True, 20.0, False),
    ],
)
def test_fan_hysteresis_uses_profile_temperature_band(
    currently_on, measurement, expected
):
    assert apply_hysteresis(
        currently_on, measurement, 20.0, 30.0, activate_below=False
    ) is expected


@pytest.mark.parametrize(
    ("currently_on", "measurement", "expected"),
    [
        (False, 60.0, False),
        (True, 60.0, True),
        (False, 39.9, True),
        (True, 80.0, False),
    ],
)
def test_humidifier_hysteresis_uses_profile_humidity_band(
    currently_on, measurement, expected
):
    assert apply_hysteresis(
        currently_on, measurement, 40.0, 80.0, activate_below=True
    ) is expected


@pytest.mark.parametrize(
    "readings",
    [
        {},
        {"bme280": {"status": "ok", "temperature": 25, "humidity": 60}},
        {
            **sensor_readings(),
            "bme680": {"status": "error", "temperature": 25, "humidity": 60},
        },
        {
            **sensor_readings(),
            "bme280": {"status": "ok", "temperature": float("nan"), "humidity": 60},
        },
    ],
)
def test_missing_or_invalid_sensor_data_returns_no_observation(readings):
    assert observe_environment(readings, PROFILE) is None


def test_invalid_profile_range_is_rejected():
    with pytest.raises(ValueError, match="Invalid profile range"):
        observe_environment(sensor_readings(), {**PROFILE, "temp_min": 31.0})


def test_hysteresis_rejects_invalid_measurements_and_ranges():
    with pytest.raises(ValueError, match="finite"):
        apply_hysteresis(False, float("nan"), 20.0, 30.0, activate_below=False)
    with pytest.raises(ValueError, match="must not exceed"):
        apply_hysteresis(False, 25.0, 30.0, 20.0, activate_below=False)
