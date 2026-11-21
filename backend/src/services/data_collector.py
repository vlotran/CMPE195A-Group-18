"""
Data collection service - runs in background
Compatible with both mock sensors and real Raspberry Pi sensors
"""

import asyncio
import html
from datetime import datetime
from typing import Optional
from types import SimpleNamespace

from backend.src.sensors.sensor_factory import SensorFactory
from backend.src.storage import db_manager
from backend.src.config.settings import settings
from backend.src.utils.logger import logger
from backend.src.services.alert_evaluator import AlertEvaluator, AlertState, METRIC_BOUNDS
from backend.src.services.actuator_controller import observe_environment
from backend.src.services.actuator_manager import actuator_manager
from backend.src.services.email_service import send_email


# Evaluator state -> DB severity. CHANGED: the DB now uses the same names as the
# evaluator and the dashboard (normal|warning|danger), so this is a 1:1 mapping.
SEVERITY_MAP = {
    AlertState.WARNING: "warning",
    AlertState.DANGER: "danger",
    AlertState.NORMAL: "normal",
}

# Display units per metric. Temperature carries both scales because the
# frontend lets users switch between C and F; stored values stay Celsius.
METRIC_UNITS = {
    "temperature": "°C",
    "humidity": "%",
    "ph": "",
    "pressure": " hPa",   # NEW
    "aqi_score": "",      # NEW
}

# NEW: metrics that should only be checked on one sensor. The BME280 also reports
# pressure, so without this both sensors would raise the same pressure alert.
METRIC_SENSORS = {
    "pressure": {"bme680"},
    "aqi_score": {"bme680"},
}

# Same names the dashboard shows (frontend/src/utils/alerts.js)
METRIC_LABELS = {
    "temperature": "Temperature",
    "humidity": "Humidity",
    "ph": "pH",
    "pressure": "Air Pressure",
    "aqi_score": "Air Quality",
}

def _c_to_f(c: float) -> float:
    """Absolute temp conversion. Not for spanning"""
    return c * 9 / 5 + 32

def _fmt_value(metric:str, value:float) -> str:
    """Format a reading for an alert message, both scales for temp"""
    if metric == "temperature":
        return f"{value:.1f} °C ({_c_to_f(value):.1f} °F)"
    
    if metric == "aqi_score":
        return f"{value:.0f}"   # NEW: whole-number score (1-4), not "3.0"
    return f"{value:.1f}{METRIC_UNITS.get(metric, '')}"
    
def _sensor_name(t) -> str:
    """'BME280 Sensor'; the pH sensor is named after its metric, so 'pH Sensor'."""
    if t.sensor_type == t.metric:
        return f"{METRIC_LABELS.get(t.metric, t.metric)} Sensor"
    return f"{t.sensor_type.upper()} Sensor"


def build_danger_email(transitions: list, dashboard_url: str = "") -> tuple[str, str, str]:
    """
    One email for every DANGER alert a user got in the same reading cycle,
    grouped by metric:

        DANGER range reached!
        Temperature:
            - BME280 Sensor: 20.6 °C (69.0 °F) (DANGER)
            - BME680 Sensor: 20.6 °C (69.0 °F) (DANGER)
        Your range: 27.0-30.0°C / 80.6-86.0°F
        [View here]

    Returns (subject, plain text, HTML). The HTML uses inline styles and a
    simple layout because mail apps strip <style> blocks and most modern CSS.
    """
    # Group by metric, in the dashboard's order (Temperature, Humidity, pH, ...)
    groups: dict[str, list] = {}
    for t in sorted(transitions, key=lambda t: (list(METRIC_LABELS).index(t.metric)
                                                if t.metric in METRIC_LABELS else 99,
                                                t.sensor_type)):
        groups.setdefault(t.metric, []).append(t)

    labels = [METRIC_LABELS.get(m, m) for m in groups]
    subject = f"DANGER range reached: {', '.join(labels)}"

    text_parts = ["DANGER range reached!", ""]
    html_sections = []
    for metric, items in groups.items():
        label = METRIC_LABELS.get(metric, metric)
        # Every sensor of one metric is checked against the same profile range
        your_range = _fmt_range(metric, items[0].threshold_min, items[0].threshold_max)

        text_parts.append(f"{label}:")
        text_parts += [f"  - {_sensor_name(t)}: {_fmt_value(metric, t.value)} (DANGER)" for t in items]
        text_parts += [f"Your range: {your_range}", ""]

        rows = "".join(
            f'<li style="margin:0 0 4px">{html.escape(_sensor_name(t))}: '
            f'{html.escape(_fmt_value(metric, t.value))} '
            f'<strong style="color:#c62828">(DANGER)</strong></li>'
            for t in items
        )
        html_sections.append(
            '<div style="margin:0 0 16px;padding:12px 16px;border:1px solid #f3c2c2;'
            'border-radius:8px;background:#fff5f5">'
            f'<p style="margin:0 0 8px;font-weight:bold">{html.escape(label)}:</p>'
            f'<ul style="margin:0 0 8px;padding-left:20px">{rows}</ul>'
            f'<p style="margin:0;color:#4b5563">Your range: {html.escape(your_range)}</p>'
            '</div>'
        )

    button = ""
    if dashboard_url:
        text_parts += [f"View here: {dashboard_url}", ""]
        button = (
            f'<p style="margin:20px 0"><a href="{html.escape(dashboard_url, quote=True)}" '
            'style="display:inline-block;padding:10px 22px;border-radius:8px;'
            'background:#e8650a;color:#ffffff;font-weight:bold;text-decoration:none">'
            'View here</a></p>'
        )
    text_parts.append("Please check your garden.")

    html_body = (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:520px;color:#1f2933">'
        '<h2 style="margin:0 0 16px;color:#c62828">DANGER range reached!</h2>'
        f'{"".join(html_sections)}{button}'
        '<p style="margin:16px 0 0;color:#4b5563">Please check your garden.</p>'
        '</div>'
    )
    return subject, "\n".join(text_parts) + "\n", html_body


def _fmt_range(metric: str, lo: float, hi: float) -> str:
    """Format a threshold range for an alert message."""
    if metric == "temperature":
        return (
            f"{lo:.1f}-{hi:.1f}°C / "
            f"{_c_to_f(lo):.1f}-{_c_to_f(hi):.1f}°F"
        )
    unit = METRIC_UNITS.get(metric, "")
    return f"{lo:.1f}-{hi:.1f}{unit}"

class DataCollector:
    """
    Background service that periodically reads sensors

    Works with:
    - Mock sensors (development)
    - Real I2C sensors (Raspberry Pi)

    Automatically adjusts behavior based on USE_MOCK_SENSORS setting
    """

    def __init__(self):
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.sensor_manager = None
        self.read_count = 0
        self.alert_count = 0
        # CHANGED (login): one evaluator per user. Each keeps its own alert state
        # (hysteresis, cooldowns), because the same reading can be DANGER for one
        # user's profile and NORMAL for another's.
        self.evaluators: dict[int, AlertEvaluator] = {}
        # {user_id: active profile}, avoids a DB read every cycle. None = reload
        self._config_cache: Optional[dict] = None
        self._warned_no_config = False # log the no-users case once
        self._warned_no_actuator_profile = False
        self._warned_invalid_actuator_readings = False
        # Running email sends. asyncio only keeps weak references to tasks, so
        # without this a send could be garbage-collected halfway through.
        self._email_tasks: set[asyncio.Task] = set()
        
    async def start(self):
        """Start background data collection"""
        if self.is_running:
            logger.warning("Data collector already running")
            return

        # Create sensor manager
        self.sensor_manager = SensorFactory.get_sensor_manager(
            use_mock=settings.use_mock_sensors
        )
        logger.info(f"Active sensors: {list(self.sensor_manager.sensors.keys())}")

        # Start background task
        self.is_running = True
        self.task = asyncio.create_task(self._collection_loop())

        sensor_type = "MOCK" if settings.use_mock_sensors else "REAL"
        logger.info(
            f"Data collector started ({sensor_type} sensors, "
            f"interval: {settings.sensor_read_interval}s)"
        )

    async def stop(self):
        """Stop background data collection"""
        if not self.is_running:
            return

        self.is_running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info(f"Data collector stopped (collected {self.read_count} readings)")

    async def _collection_loop(self):
        """
        Main collection loop

        Continuously reads sensors at configured interval
        Works identically for mock and real sensors
        """
        logger.info("Starting sensor collection loop...")

        while self.is_running:
            try:
                await self._read_and_store()

                # Wait for next interval
                await asyncio.sleep(settings.sensor_read_interval)

            except asyncio.CancelledError:
                logger.info("Collection loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                # Continue despite errors (important for reliability)
                await asyncio.sleep(settings.sensor_read_interval)

    async def _read_and_store(self):
        """
        Read all sensors and store in database

        This method works identically whether sensors are mock or real
        The sensor_manager abstraction handles the difference
        """
        try:
            # Read all sensors (mock or real)
            readings = await self.sensor_manager.read_all()

            # Store each reading
            stored_count = 0
            for sensor_type, data in readings.items():
                if data.get("status") == "ok":
                    try:
                        await db_manager.insert_sensor_reading(sensor_type, data)
                        stored_count += 1
                    except Exception as e:
                        logger.error(f"Failed to store {sensor_type} reading: {e}")

            self.read_count += stored_count

            await self._evaluate_alerts(readings) 
            await self._observe_actuator_control(readings)
            await actuator_manager.evaluate_automatic(readings)

            if stored_count > 0:
                logger.debug(
                    f"Stored {stored_count} readings " f"(total: {self.read_count})"
                )

        except Exception as e:
            logger.error(f"Error reading/storing sensors: {e}")

    def get_status(self) -> dict:
        """Get collector status"""
        return {
            "is_running": self.is_running,
            "total_readings": self.read_count,
            "total_alerts": self.alert_count,
            "using_mock": settings.use_mock_sensors,
            "interval_seconds": settings.sensor_read_interval,
            "actuator_control": {
                "mode": (
                    "observation_only"
                    if settings.actuator_profile_user_id is not None
                    else "disabled"
                ),
                "profile_user_id": settings.actuator_profile_user_id,
                "gpio_enabled": False,
            },
        }

    def invalidate_config(self, user_id: Optional[int] = None):
        """
        Called when a user's active threshold profile changes
        (DANGER state at one profile can be NORMAL in another one when switching)

        (login): user_id -> reset only that user's alert state.
        No user_id (e.g. a new account) -> just reload the profile list.
        """
        self._config_cache = None
        self._warned_no_config = False
        self._warned_no_actuator_profile = False
        if user_id is not None:
            evaluator = self.evaluators.get(user_id)
            if evaluator:
                evaluator.reset()
            logger.info(f"Threshold profile changed for user {user_id} - alert state reset")

    async def _get_configs(self) -> dict:
        """
        CHANGED (login): every user's active profile as {user_id: config},
        cached until invalidate_config()
        """
        if self._config_cache is None:
            rows = await db_manager.get_all_active_configurations()
            # Db returns dicts; evaluator reads attributes
            self._config_cache = {row["user_id"]: SimpleNamespace(**row) for row in rows}
            # Forget evaluators of users who no longer have an active profile
            for uid in list(self.evaluators):
                if uid not in self._config_cache:
                    del self.evaluators[uid]
        return self._config_cache

    async def _observe_actuator_control(self, readings: dict):
        """Log sensor averages and targets only; this path never controls GPIO."""
        user_id = settings.actuator_profile_user_id
        if user_id is None:
            return

        config = (await self._get_configs()).get(user_id)
        if config is None:
            if not self._warned_no_actuator_profile:
                logger.warning(
                    "Actuator observation disabled: no active profile for "
                    f"configured user {user_id}"
                )
                self._warned_no_actuator_profile = True
            return

        observation = observe_environment(readings, vars(config))
        if observation is None:
            if not self._warned_invalid_actuator_readings:
                logger.warning(
                    "Actuator observation skipped: valid BME280 and BME680 "
                    "temperature and humidity readings are required"
                )
                self._warned_invalid_actuator_readings = True
            return

        self._warned_no_actuator_profile = False
        self._warned_invalid_actuator_readings = False
        logger.info(
            "Actuator observation only (GPIO disabled): "
            f"user={user_id}, temperature={observation.temperature_c:.2f}°C "
            f"(range {observation.temperature_min_c:.2f}-"
            f"{observation.temperature_max_c:.2f}°C), "
            f"humidity={observation.humidity_pct:.2f}% "
            f"(range {observation.humidity_min_pct:.2f}-"
            f"{observation.humidity_max_pct:.2f}%)"
        )

    async def _evaluate_alerts(self, readings: dict):
        """
        Check each reading against EVERY user's active thresholds and persist
        any confirmed state changes, tagged with that user.

        Never raises - alerting problems must not stop data collection.
        """
        configs = await self._get_configs()
        if not configs:
            if not self._warned_no_config:
                logger.warning("No user has an active threshold profile - alerts disabled")
                self._warned_no_config = True
            return

        # DANGER alerts from this cycle, per user, so each user gets ONE email
        # even when several sensors cross into DANGER together
        dangers: dict[int, list] = {}

        for user_id, config in configs.items():
            evaluator = self.evaluators.setdefault(user_id, AlertEvaluator())

            for sensor_type, data in readings.items():
                if data.get("status") != "ok":
                    continue

                # A sensor may report several metrics (BME280: temp + humidity)
                for metric in METRIC_BOUNDS:
                    if metric not in data:
                        continue
                    # skip metrics this sensor isn't the source of
                    allowed = METRIC_SENSORS.get(metric)
                    if allowed and sensor_type not in allowed:
                        continue

                    transition = evaluator.evaluate(
                        sensor_type, metric, data[metric], config
                    )
                    if transition:
                        await self._record_alert(transition, user_id)
                        if transition.should_notify:
                            dangers.setdefault(user_id, []).append(transition)

        for user_id, transitions in dangers.items():
            self._queue_danger_email(user_id, transitions)

    async def _record_alert(self, t, user_id: int):
        """Persist one transition, and notify if it warrants it."""
        recovered = t.to_state == AlertState.NORMAL
        message = (
            f"{t.sensor_type} {t.metric} back to normal: "
            f"{_fmt_value(t.metric, t.value)}"
            if recovered
            else f"{t.sensor_type} {t.metric} is {t.to_state.value.upper()}: "
                    f"{_fmt_value(t.metric, t.value)} "
                    f"(range {_fmt_range(t.metric, t.threshold_min, t.threshold_max)})"
        )

        try:
            await db_manager.create_alert({
                "user_id": user_id,  #login: whose profile raised it
                "alert_type": "recovery" if recovered else "threshold_breach",
                "sensor_type": t.sensor_type,
                "message": message,
                "severity": SEVERITY_MAP[t.to_state],
                "reading_value": t.value,
                "threshold_min": t.threshold_min,
                "threshold_max": t.threshold_max,
            })
            self.alert_count += 1
            logger.info(f"Alert (user {user_id}): {message}")
        except Exception as e:
            # Log and move on, a failed alert insert must not cost us readings
            logger.error(f"Failed to store alert for {t.sensor_type} (user {user_id}): {e}")

        if t.should_notify:
            # TODO(Phase 4): web push
            logger.warning(f"DANGER: {message}")
            # The email is sent once per cycle by _evaluate_alerts, not here

    def _queue_danger_email(self, user_id: int, transitions: list):
        """
        Send one email for this user's DANGER alerts, in the background:
        slow SMTP must not delay the next sensor reading.
        """
        if not settings.smtp_username:
            return  # email is turned off
        task = asyncio.create_task(self._email_danger_alerts(transitions, user_id))
        self._email_tasks.add(task)
        task.add_done_callback(self._email_tasks.discard)

    async def _email_danger_alerts(self, transitions: list, user_id: int):
        """Email the alerts to the user who owns the profile. Never raises."""
        try:
            to = await db_manager.get_user_email(user_id)
            if to is None:
                return
            subject, text, html_body = build_danger_email(transitions, settings.dashboard_url)
            await send_email(to, subject, text, html_body)
        except Exception as e:
            logger.error(f"Could not email alert to user {user_id}: {e}")

# Singleton instance
data_collector = DataCollector()