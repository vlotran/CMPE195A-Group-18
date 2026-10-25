"""Standalone, manual, one-channel-at-a-time Raspberry Pi relay test.

Run on the Pi with: python3 relay_test.py

Disconnect actuator loads before testing. This script uses BCM GPIO numbering,
does not integrate with the application controller, and controls only the
channel you select. A selected channel stays on until you turn it off, go back,
or exit the program.
"""

from importlib import import_module
from typing import Optional


RELAYS = {
    "1": ("Mechanical relay IN1 (GPIO21)", 21, False),
    "2": ("Mechanical relay IN2 (GPIO20)", 20, False),
    "3": ("SSR IN1 / CH1 (GPIO16)", 16, False),
    "4": ("SSR IN2 / CH2 (GPIO12)", 12, False),
}


def _selected_relay() -> Optional[tuple[str, int, bool]]:
    print("\nRelay channels (BCM GPIO numbering):")
    for key, (name, pin, active_high) in RELAYS.items():
        polarity = "active-high" if active_high else "active-low"
        print(f"  {key}. {name} [{polarity}]")
    print("  q. Quit")

    while True:
        choice = input("Select one relay to test: ").strip().lower()
        if choice == "q":
            return None
        if choice in RELAYS:
            name, pin, active_high = RELAYS[choice]
            return name, pin, active_high
        print("Select 1, 2, 3, 4, or q.")


def _control_relay(name: str, pin: int, active_high: bool) -> None:
    try:
        output_device = import_module("gpiozero").OutputDevice
    except ImportError as exc:
        raise SystemExit(
            "gpiozero is required on the Raspberry Pi. Install it with "
            "'sudo apt install python3-gpiozero'."
        ) from exc

    relay = output_device(pin, active_high=active_high, initial_value=False)
    try:
        print(f"{name} is configured OFF on BCM GPIO{pin}.")
        while True:
            command = input(
                "Enter ON to energize, OFF to de-energize, or BACK to choose "
                "another channel: "
            ).strip().upper()
            if command == "ON":
                relay.on()
                print(f"{name} is ON. It will stay on until you enter OFF or BACK.")
            elif command == "OFF":
                relay.off()
                print(f"{name} is OFF.")
            elif command == "BACK":
                break
            else:
                print("Enter ON, OFF, or BACK.")
    finally:
        relay.off()
        relay.close()


def main() -> None:
    print(
        "SAFETY: disconnect actuator loads and keep mains/high voltage "
        "disconnected while testing."
    )
    try:
        while True:
            selected = _selected_relay()
            if selected is None:
                print("Exiting; all selected relays are OFF.")
                return
            name, pin, active_high = selected
            _control_relay(name, pin, active_high)
    except KeyboardInterrupt:
        print("\nInterrupted; selected relay is being switched OFF.")


if __name__ == "__main__":
    main()
