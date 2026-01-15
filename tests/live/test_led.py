#!/usr/bin/env python3
"""
Interactive TJBot LED Hardware Test

This test validates LED functionality through user interaction.
It tests both NeoPixel and Common Anode LEDs using the TJBot API.
"""

import sys
import os

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

from tjbot import TJBot
from tjbot.rpi_drivers.rpi_detect import RPiDetect

try:
    from .utils import format_title, format_section, confirm, prompt_input, select_option
except ImportError:
    from utils import format_title, format_section, confirm, prompt_input, select_option


def run_test():
    """Run interactive LED test"""
    print(format_title("TJBot LED Hardware Test"))

    # Ask user which LED type to test
    led_type = select_option(
        "Which LED type are you testing?",
        [
            {"name": "NeoPixel (WS2812B)", "value": "neopixel"},
            {"name": "Common Anode RGB LED", "value": "common-anode"},
        ],
        default="neopixel"
    )

    is_neopixel = led_type == "neopixel"

    config = {
        "log": {"level": "info"},
        "hardware": {},
        "shine": {}
    }

    if is_neopixel:
        # NeoPixel setup - configuration varies by Pi model
        if RPiDetect.is_pi5():
            # RPi5 uses SPI interface
            spi_interface = prompt_input(
                "Enter SPI interface for NeoPixel LED (default: /dev/spidev0.0)",
                "/dev/spidev0.0"
            )
            config["shine"]["neopixel"] = {"spiInterface": spi_interface}
            print(f"✓ NeoPixel SPI interface: {spi_interface}\n")
        else:
            # RPi3/4 use GPIO pin
            gpio_pin = prompt_input(
                "Enter GPIO pin for NeoPixel LED (default: 21)",
                "21"
            )
            config["shine"]["neopixel"] = {"gpioPin": int(gpio_pin)}
            print(f"✓ NeoPixel GPIO pin: {gpio_pin}\n")

        config["hardware"]["led_neopixel"] = True
        print("✓ NeoPixel LED config ready\n")
    else:
        # Common Anode RGB LED setup
        red_pin = prompt_input("Enter GPIO pin for Red LED (default: 19)", "19")
        green_pin = prompt_input("Enter GPIO pin for Green LED (default: 13)", "13")
        blue_pin = prompt_input("Enter GPIO pin for Blue LED (default: 12)", "12")

        config["hardware"]["led_common_anode"] = True
        config["shine"]["commonanode"] = {
            "redPin": int(red_pin),
            "greenPin": int(green_pin),
            "bluePin": int(blue_pin)
        }
        print("✓ Common Anode LED config ready\n")

    # Initialize TJBot with the configuration
    tjbot = TJBot(config)

    if config["hardware"].get("led_neopixel"):
        print("✓ TJBot initialized with NeoPixel LED\n")
    else:
        ca_config = config["shine"]["commonanode"]
        print(
            f"✓ TJBot initialized with Common Anode LED on "
            f"Red:GPIO{ca_config['redPin']} "
            f"Green:GPIO{ca_config['greenPin']} "
            f"Blue:GPIO{ca_config['bluePin']}\n"
        )

    print(format_section("Testing TJBot Shine API"))

    try:
        results = []

        # Test 1: Red LED
        print("Test 1: Shining RED")
        tjbot.shine("red")
        result = confirm("Did the LED turn RED?")
        print("✓ PASS" if result else "✗ FAIL")
        results.append(result)

        # Test 2: Green LED
        print("\nTest 2: Shining GREEN")
        tjbot.shine("green")
        result = confirm("Did the LED turn GREEN?")
        print("✓ PASS" if result else "✗ FAIL")
        results.append(result)

        # Test 3: Blue LED
        print("\nTest 3: Shining BLUE")
        tjbot.shine("blue")
        result = confirm("Did the LED turn BLUE?")
        print("✓ PASS" if result else "✗ FAIL")
        results.append(result)

        # Test 4: Purple (hex color)
        print("\nTest 4: Shining PURPLE (hex #9400D3)")
        tjbot.shine("#9400D3")
        result = confirm("Did the LED turn PURPLE?")
        print("✓ PASS" if result else "✗ FAIL")
        results.append(result)

        # Test 5: Pulse
        print("\nTest 5: Pulsing YELLOW (1 second)")
        tjbot.pulse("yellow", duration=1.0)
        result = confirm("Did the LED pulse YELLOW?")
        print("✓ PASS" if result else "✗ FAIL")
        results.append(result)

        # Turn off LED
        print("\nTurning off LED...")
        tjbot.shine("off")

        print(format_title("LED Test Complete"))

        # Summary
        passed = sum(results)
        total = len(results)
        print(f"Results: {passed}/{total} tests passed")

        if passed != total:
            sys.exit(1)

    except Exception as error:
        print(f"\n✗ Error during LED test: {error}")
        sys.exit(1)


if __name__ == "__main__":
    run_test()
