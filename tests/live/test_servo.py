#!/usr/bin/env python3
"""
Interactive TJBot Servo Hardware Test

This test validates servo motor functionality through user interaction.
"""

import sys
import os

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

from tjbot import TJBot

try:
    from .utils import (
        format_title,
        format_section,
        confirm_user,
        prompt_user,
    )
except ImportError:
    from utils import (
        format_title,
        format_section,
        confirm_user,
        prompt_user,
    )


def run_test():
    """Run interactive servo test"""
    print(format_title("TJBot Servo Hardware Test"))

    # Ask user which GPIO pin the servo is connected to
    gpio_input = prompt_user("Enter GPIO pin for servo (default: 18): ")
    servo_pin = 18 if gpio_input.strip() == "" else int(gpio_input.strip())

    tjbot = TJBot({
        "log": {"level": "info"},
        "wave": {
            "servoPin": servo_pin,
        },
        "hardware": {
            "servo": True
        }
    })

    print(format_section("Testing TJBot Wave API"))

    try:
        print(f"✓ TJBot initialized with servo hardware on GPIO{tjbot.config.wave.servoPin}\n")

        # Test 1: Arm back
        print("Test 1: Moving arm to BACK position")
        tjbot.arm_back()
        result1 = confirm_user("Did the arm move to the BACK position? (yes/no): ")
        print("✓ PASS" if result1 else "✗ FAIL")

        # Test 2: Raise arm
        print("\nTest 2: RAISING the arm")
        tjbot.raise_arm()
        result2 = confirm_user("Did the arm RAISE UP? (yes/no): ")
        print("✓ PASS" if result2 else "✗ FAIL")

        # Test 3: Lower arm
        print("\nTest 3: LOWERING the arm")
        tjbot.lower_arm()
        result3 = confirm_user("Did the arm LOWER DOWN? (yes/no): ")
        print("✓ PASS" if result3 else "✗ FAIL")

        # Test 4: Wave
        print("\nTest 4: WAVING the arm")
        tjbot.wave()
        result4 = confirm_user("Did the arm WAVE back and forth? (yes/no): ")
        print("✓ PASS" if result4 else "✗ FAIL")

        # Return to back position
        print("\nReturning arm to upward position...")
        tjbot.raise_arm()

        print(format_title("Servo Test Complete"))

    except Exception as error:
        print(f"\n✗ Error during servo test: {error}")
        sys.exit(1)


if __name__ == "__main__":
    run_test()

