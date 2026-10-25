"""Tests for the standalone interactive relay test utility."""

import builtins
import sys
import types

from relay_test import RELAYS, _control_relay


def test_manual_commands_control_only_selected_channel_and_leave_it_off(monkeypatch):
    devices = []

    class FakeOutputDevice:
        def __init__(self, pin, active_high, initial_value):
            self.pin = pin
            self.active_high = active_high
            self.state = initial_value
            self.closed = False
            devices.append(self)

        def on(self):
            self.state = True

        def off(self):
            self.state = False

        def close(self):
            self.closed = True

    monkeypatch.setitem(
        sys.modules,
        "gpiozero",
        types.SimpleNamespace(OutputDevice=FakeOutputDevice),
    )
    commands = iter(["ON", "OFF", "BACK"])
    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        return next(commands)

    monkeypatch.setattr(builtins, "input", fake_input)

    _control_relay("SSR CH1", pin=16, active_high=False)

    assert len(devices) == 1
    assert devices[0].pin == 16
    assert devices[0].active_high is False
    assert devices[0].state is False
    assert devices[0].closed is True
    assert len(prompts) == 3


def test_back_turns_off_a_channel_that_was_left_on(monkeypatch):
    states = []
    configured = []

    class FakeOutputDevice:
        def __init__(self, pin, active_high, initial_value):
            configured.append((pin, active_high))
            self.state = initial_value

        def on(self):
            self.state = True

        def off(self):
            self.state = False
            states.append(self.state)

        def close(self):
            pass

    monkeypatch.setitem(
        sys.modules,
        "gpiozero",
        types.SimpleNamespace(OutputDevice=FakeOutputDevice),
    )
    commands = iter(["ON", "BACK"])
    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        return next(commands)

    monkeypatch.setattr(builtins, "input", fake_input)

    _control_relay("Mechanical IN1", pin=21, active_high=False)

    assert states == [False]
    assert configured == [(21, False)]
    assert len(prompts) == 2


def test_all_relay_channels_are_configured_active_low():
    assert all(active_high is False for _, _, active_high in RELAYS.values())
