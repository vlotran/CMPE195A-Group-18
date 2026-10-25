"""Authenticated shared-Pi actuator controls."""

from datetime import time
from typing import NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.src.api.routes.auth import get_current_user
from backend.src.services.actuator_manager import actuator_manager
from backend.src.utils.logger import logger

router = APIRouter(prefix="/api/actuators", tags=["actuators"])


class OutputCommand(BaseModel):
    on: bool


class LightScheduleRequest(BaseModel):
    enabled: bool
    start: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")

    @field_validator("start", "end")
    @classmethod
    def validate_wall_time(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            try:
                time.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("Time must be a valid 24-hour HH:MM value") from exc
        return value

    @model_validator(mode="after")
    def require_distinct_times_when_enabled(self):
        if self.enabled and (self.start is None or self.end is None):
            raise ValueError("Start and end times are required to enable the schedule")
        if self.enabled and self.start == self.end:
            raise ValueError("Schedule start and end times must differ")
        return self


def _raise_control_error(exc: Exception) -> NoReturn:
    logger.error(f"Actuator control request failed: {exc}")
    if isinstance(exc, RuntimeError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=503, detail="Actuator control is unavailable") from exc


@router.get("/")
async def get_actuator_state(_user: dict = Depends(get_current_user)):
    """Return shared outputs, schedule, and hardware-availability status."""
    return await actuator_manager.get_state()


@router.post("/{actuator}/state")
async def set_actuator_state(
    actuator: str,
    command: OutputCommand,
    _user: dict = Depends(get_current_user),
):
    """Manually switch one mapped relay; all signed-in users share this state."""
    if actuator not in {"fan", "humidifier", "grow_light"}:
        raise HTTPException(status_code=404, detail="Unknown actuator")
    try:
        return await actuator_manager.set_output(actuator, command.on)
    except Exception as exc:
        _raise_control_error(exc)


@router.put("/light-schedule")
async def set_light_schedule(
    schedule: LightScheduleRequest,
    _user: dict = Depends(get_current_user),
):
    """Save or enable the shared daily light schedule in Pi local time."""
    try:
        return await actuator_manager.set_light_schedule(
            schedule.enabled, schedule.start, schedule.end
        )
    except Exception as exc:
        _raise_control_error(exc)


@router.post("/automatic")
async def set_automatic_control(
    enabled: bool = True,
    user: dict = Depends(get_current_user),
):
    """Enable or disable profile-band hysteresis control for this user."""
    try:
        return await actuator_manager.set_automatic(enabled, user["id"])
    except Exception as exc:
        _raise_control_error(exc)
