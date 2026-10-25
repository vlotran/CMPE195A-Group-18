"""Hardware-independent hysteresis rules for temperature and humidity."""

from dataclasses import dataclass
import math
from typing import Mapping, Optional


@dataclass(frozen=True)
class EnvironmentalObservation:
    """Averaged sensor readings and active-profile control bands."""

    temperature_c: float
    humidity_pct: float
    temperature_min_c: float
    temperature_max_c: float
    humidity_min_pct: float
    humidity_max_pct: float


def _average_sensor_value(readings: Mapping[str, Mapping], metric: str) -> Optional[float]:
    values = []
    for sensor_id in ("bme280", "bme680"):
        reading = readings.get(sensor_id)
        if not reading or reading.get("status") != "ok":
            return None
        value = reading.get(metric)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(value):
            return None
        values.append(float(value))
    return sum(values) / len(values)


def _profile_range(
    profile: Mapping[str, float], minimum: str, maximum: str
) -> tuple[float, float]:
    low = profile[minimum]
    high = profile[maximum]
    if not math.isfinite(low) or not math.isfinite(high) or low > high:
        raise ValueError(f"Invalid profile range: {minimum}/{maximum}")
    return low, high


def apply_hysteresis(
    currently_on: bool,
    measurement: float,
    minimum: float,
    maximum: float,
    *,
    activate_below: bool,
) -> bool:
    """Preserve state within the profile band and switch at its outer edges."""
    if not all(math.isfinite(value) for value in (measurement, minimum, maximum)):
        raise ValueError("Measurement and profile limits must be finite")
    if minimum > maximum:
        raise ValueError("Profile minimum must not exceed maximum")

    if activate_below:
        if measurement < minimum:
            return True
        if measurement >= maximum:
            return False
    else:
        if measurement > maximum:
            return True
        if measurement <= minimum:
            return False
    return currently_on


def observe_environment(
    readings: Mapping[str, Mapping], profile: Mapping[str, float]
) -> Optional[EnvironmentalObservation]:
    """Combine valid BME readings with profile bands for automatic control."""
    temperature = _average_sensor_value(readings, "temperature")
    humidity = _average_sensor_value(readings, "humidity")
    if temperature is None or humidity is None:
        return None

    temperature_min, temperature_max = _profile_range(
        profile, "temp_min", "temp_max"
    )
    humidity_min, humidity_max = _profile_range(
        profile, "humidity_min", "humidity_max"
    )
    return EnvironmentalObservation(
        temperature_c=temperature,
        humidity_pct=humidity,
        temperature_min_c=temperature_min,
        temperature_max_c=temperature_max,
        humidity_min_pct=humidity_min,
        humidity_max_pct=humidity_max,
    )
