"""Shared manual actuator outputs and grow-light schedule for the Pi."""

import asyncio
from datetime import datetime, time as wall_time
from importlib import import_module
from typing import Optional

from backend.src.config.settings import settings
from backend.src.storage import db_manager
from backend.src.services.actuator_controller import (
    apply_hysteresis,
    observe_environment,
)
from backend.src.utils.logger import logger


AUTOMATIC_MIN_SWITCH_INTERVAL_SECONDS = 30

ACTUATOR_PINS = {
    "fan": 16,
    "humidifier": 20,
    "grow_light": 21,
}


class ActuatorManager:
    """Manage the single Pi's manual outputs and profile-based automation.

    GPIO hardware support is opt-in. The grow-light schedule uses Pi local time.
    Automatic environment control uses profile-band hysteresis.
    """

    def __init__(self) -> None:
        self._devices = {}
        self._lock = asyncio.Lock()
        self._schedule_task: Optional[asyncio.Task] = None
        self._automatic_user_id: Optional[int] = None
        self._last_automatic_switch = {"fan": 0.0, "humidifier": 0.0}

    async def start(self) -> None:
        """Initialize outputs OFF and start schedule evaluation."""
        self._automatic_user_id = None
        async with self._lock:
            if settings.actuator_hardware_enabled:
                self._initialize_gpio()
                for device in self._devices.values():
                    device.off()
                await db_manager.update_actuator_state(
                    {"fan_on": False, "humidifier_on": False, "grow_light_on": False}
                )
                logger.warning("Actuator GPIO enabled; all relay outputs initialized OFF")
            else:
                await db_manager.update_actuator_state(
                    {
                        "fan_on": False,
                        "humidifier_on": False,
                        "grow_light_on": False,
                        "light_schedule_enabled": False,
                    }
                )
                logger.info("Actuator GPIO disabled by ACTUATOR_HARDWARE_ENABLED")
        if self._schedule_task is None or self._schedule_task.done():
            self._schedule_task = asyncio.create_task(self._schedule_loop())

    async def stop(self) -> None:
        """Stop schedule evaluation and de-energize/close GPIO devices."""
        if self._schedule_task is not None:
            self._schedule_task.cancel()
            try:
                await self._schedule_task
            except asyncio.CancelledError:
                pass
            self._schedule_task = None

        async with self._lock:
            for device in self._devices.values():
                device.off()
                device.close()
            self._devices.clear()

    def _initialize_gpio(self) -> None:
        if self._devices:
            return
        try:
            output_device = import_module("gpiozero").OutputDevice
        except ImportError as exc:
            raise RuntimeError(
                "GPIO is enabled but gpiozero is unavailable in the backend "
                "Python environment"
            ) from exc

        try:
            for name, pin in ACTUATOR_PINS.items():
                self._devices[name] = output_device(
                    pin, active_high=False, initial_value=False
                )
        except Exception:
            for device in self._devices.values():
                device.off()
                device.close()
            self._devices.clear()
            raise

    async def get_state(self) -> dict:
        state = await db_manager.get_actuator_state()
        automatic_available = (
            settings.actuator_hardware_enabled and not settings.use_mock_sensors
        )
        return {
            "fan_on": state["fan_on"],
            "humidifier_on": state["humidifier_on"],
            "grow_light_on": state["grow_light_on"],
            "light_schedule_enabled": state["light_schedule_enabled"],
            "light_start": state["light_start"],
            "light_end": state["light_end"],
            "hardware_enabled": settings.actuator_hardware_enabled,
            "automatic_enabled": self._automatic_user_id is not None,
            "automatic_available": automatic_available,
            "automatic_block_reason": (
                ""
                if automatic_available
                else (
                    "Automatic control requires real sensors and "
                    "ACTUATOR_HARDWARE_ENABLED=True."
                )
            ),
            "automatic_min_switch_interval_seconds": (
                AUTOMATIC_MIN_SWITCH_INTERVAL_SECONDS
            ),
            "timezone": "Pi local time",
        }

    async def set_automatic(self, enabled: bool, user_id: int) -> dict:
        """Enable profile-based on/off control for one signed-in user."""
        if enabled and not settings.actuator_hardware_enabled:
            raise RuntimeError(
                "Physical actuator control is disabled. Set "
                "ACTUATOR_HARDWARE_ENABLED=True on the Pi to enable it."
            )
        if enabled and settings.use_mock_sensors:
            raise RuntimeError(
                "Automatic control cannot run with mock sensor readings."
            )

        profile = await db_manager.get_active_configuration(user_id) if enabled else None
        if enabled and profile is None:
            raise RuntimeError(
                "Choose an active temperature and humidity profile before "
                "enabling automatic control."
            )

        async with self._lock:
            if enabled:
                if self._automatic_user_id != user_id:
                    self._initialize_gpio()
                    for actuator in ("fan", "humidifier"):
                        self._devices[actuator].off()
                    await db_manager.update_actuator_state(
                        {"fan_on": False, "humidifier_on": False}
                    )
                    now = asyncio.get_running_loop().time()
                    self._last_automatic_switch = {"fan": now, "humidifier": now}
                    self._automatic_user_id = user_id
            else:
                self._automatic_user_id = None
                if settings.actuator_hardware_enabled:
                    self._initialize_gpio()
                    for actuator in ("fan", "humidifier"):
                        self._devices[actuator].off()
                await db_manager.update_actuator_state(
                    {"fan_on": False, "humidifier_on": False}
                )
        return await self.get_state()

    async def evaluate_automatic(self, readings: dict) -> None:
        """Apply profile-band hysteresis to valid sensor readings."""
        async with self._lock:
            user_id = self._automatic_user_id
            if user_id is None:
                return

            profile = await db_manager.get_active_configuration(user_id)
            if profile is None:
                logger.error(
                    "Automatic control stopped: enabling user's active profile "
                    f"is unavailable (user {user_id})"
                )
                self._automatic_user_id = None
                await self._set_automatic_outputs_off()
                return

            try:
                observation = observe_environment(readings, profile)
            except (KeyError, TypeError, ValueError) as exc:
                logger.error(f"Automatic control stopped for invalid profile: {exc}")
                self._automatic_user_id = None
                await self._set_automatic_outputs_off()
                return

            if observation is None:
                logger.warning(
                    "Automatic control sensor readings unavailable; "
                    "turning fan and humidifier OFF"
                )
                await self._set_automatic_outputs_off()
                return

            state = await db_manager.get_actuator_state()
            desired = {
                "fan": apply_hysteresis(
                    state["fan_on"],
                    observation.temperature_c,
                    observation.temperature_min_c,
                    observation.temperature_max_c,
                    activate_below=False,
                ),
                "humidifier": apply_hysteresis(
                    state["humidifier_on"],
                    observation.humidity_pct,
                    observation.humidity_min_pct,
                    observation.humidity_max_pct,
                    activate_below=True,
                ),
            }
            now = asyncio.get_running_loop().time()
            for actuator, should_be_on in desired.items():
                state_field = f"{actuator}_on"
                if should_be_on == state[state_field]:
                    continue
                if (
                    now - self._last_automatic_switch[actuator]
                    < AUTOMATIC_MIN_SWITCH_INTERVAL_SECONDS
                ):
                    continue
                self._initialize_gpio()
                device = self._devices[actuator]
                device.on() if should_be_on else device.off()
                await db_manager.update_actuator_state(
                    {state_field: should_be_on}
                )
                self._last_automatic_switch[actuator] = now

    async def _set_automatic_outputs_off(self) -> None:
        """Fail off without applying the normal minimum-switch interval."""
        state = await db_manager.get_actuator_state()
        updates = {}
        if settings.actuator_hardware_enabled:
            self._initialize_gpio()
        for actuator in ("fan", "humidifier"):
            if settings.actuator_hardware_enabled:
                self._devices[actuator].off()
            if state[f"{actuator}_on"]:
                updates[f"{actuator}_on"] = False
            self._last_automatic_switch[actuator] = (
                asyncio.get_running_loop().time()
            )
        if updates:
            await db_manager.update_actuator_state(updates)

    async def set_output(self, actuator: str, on: bool) -> dict:
        if actuator not in ACTUATOR_PINS:
            raise ValueError(f"Unknown actuator: {actuator}")
        if on and not settings.actuator_hardware_enabled:
            raise RuntimeError(
                "Physical actuator control is disabled. Set "
                "ACTUATOR_HARDWARE_ENABLED=True on the Pi to enable it."
            )

        state_field = f"{actuator}_on"
        async with self._lock:
            if actuator in {"fan", "humidifier"}:
                self._automatic_user_id = None
            if settings.actuator_hardware_enabled:
                self._initialize_gpio()
                device = self._devices[actuator]
                try:
                    device.on() if on else device.off()
                except Exception:
                    device.off()
                    raise
            updates = {state_field: on}
            if actuator == "grow_light":
                updates["light_schedule_enabled"] = False
            try:
                await db_manager.update_actuator_state(updates)
            except Exception:
                if settings.actuator_hardware_enabled:
                    self._devices[actuator].off()
                raise
        return await self.get_state()

    async def set_light_schedule(
        self, enabled: bool, start: Optional[str], end: Optional[str]
    ) -> dict:
        if enabled and not settings.actuator_hardware_enabled:
            raise RuntimeError(
                "Physical actuator control is disabled. Set "
                "ACTUATOR_HARDWARE_ENABLED=True on the Pi to enable schedules."
            )
        await db_manager.update_actuator_state(
            {
                "light_schedule_enabled": enabled,
                "light_start": start,
                "light_end": end,
            }
        )
        if enabled:
            await self._apply_light_schedule()
        return await self.get_state()

    @staticmethod
    def _schedule_is_on(now: wall_time, start: str, end: str) -> bool:
        start_time = wall_time.fromisoformat(start)
        end_time = wall_time.fromisoformat(end)
        if start_time < end_time:
            return start_time <= now < end_time
        return now >= start_time or now < end_time

    async def _apply_light_schedule(self) -> None:
        if not settings.actuator_hardware_enabled:
            return
        async with self._lock:
            state = await db_manager.get_actuator_state()
            if not state["light_schedule_enabled"]:
                return
            start = state["light_start"]
            end = state["light_end"]
            if not start or not end:
                logger.error("Grow-light schedule is enabled without start/end times")
                return
            should_be_on = self._schedule_is_on(datetime.now().time(), start, end)
            self._initialize_gpio()
            if should_be_on:
                self._devices["grow_light"].on()
            else:
                self._devices["grow_light"].off()
            await db_manager.update_actuator_state({"grow_light_on": should_be_on})

    async def _schedule_loop(self) -> None:
        while True:
            try:
                await self._apply_light_schedule()
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(f"Grow-light schedule evaluation failed: {exc}")
                await asyncio.sleep(5)


actuator_manager = ActuatorManager()
