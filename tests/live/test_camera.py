#!/usr/bin/env python3
"""
Interactive TJBot Camera Hardware Test

This test validates camera functionality through the TJBot API.
"""

import sys
import os

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

from tjbot import TJBot
from tjbot.camera import CameraController

try:
    from .utils import (
        format_title,
        format_section,
        is_command_available,
    )
except ImportError:
    from utils import (
        format_title,
        format_section,
        is_command_available,
    )


def run_test():
    """Run interactive camera test"""
    print(format_title("TJBot Camera Hardware Test"))

    # Check for required dependencies
    print("Checking for required dependencies...")

    if is_command_available("rpicam-still"):
        print("✓ rpicam-still command available")
    else:
        print("✗ rpicam-still command not available")
        print("\nInstall with:")
        print("  sudo apt-get install rpicam-apps-lite\n")
        sys.exit(1)

    print("✓ All dependencies available\n")

    # Test TJBot.look() API
    print(format_section("Testing TJBot Look API"))

    tjbot = TJBot({"log": {"level": "info"}})

    try:
        tjbot._initialize_hardware_from_config()
        # Manually setup camera since it's not in default hardware config
        tjbot.rpi_driver.setup_camera(tjbot.config.see)
        print("✓ TJBot initialized with camera hardware\n")

        # Test 1: Take photo with default path via tjbot.look()
        print("\nTest 1: Taking a photo via tjbot.look() (default path)")
        photo_path_1 = tjbot.look()
        print(f"Photo saved to: {photo_path_1}")

        assert os.path.exists(photo_path_1), "Photo file was not created at default path"
        print("✓ PASS - Photo file created")

        # Test 2: Take photo with custom path via tjbot.look()
        print("\nTest 2: Taking a photo via tjbot.look() (custom path)")
        custom_path = "/tmp/tjbot-test-photo.jpg"
        photo_path_2 = tjbot.look(custom_path)
        print(f"Photo saved to: {photo_path_2}")

        assert os.path.exists(photo_path_2), "Photo file was not created at custom path"
        assert photo_path_2 == custom_path, "Photo path does not match requested custom path"
        print("✓ PASS - Photo file created at custom path")

        # Test 3: Multiple photos via tjbot.look()
        print("\nTest 3: Taking multiple photos in sequence via tjbot.look()")
        photo_3 = tjbot.look()
        print(f"Photo 3: {photo_3}")
        photo_4 = tjbot.look()
        print(f"Photo 4: {photo_4}")

        assert os.path.exists(photo_3), "Photo 3 file was not created"
        assert os.path.exists(photo_4), "Photo 4 file was not created"
        assert photo_3 != photo_4, "Multiple photos should have different paths"
        print("✓ PASS - Multiple photos captured successfully")

    except Exception as error:
        print(f"\n✗ Error during TJBot.look() test: {error}")
        print("\nMake sure:")
        print("  1. You are running on a Raspberry Pi")
        print("  2. rpicam-still command-line tool is installed")
        print("     Install with: sudo apt-get install rpicam-apps-lite")
        print("  3. Camera hardware is properly connected")
        print("  4. Camera interface is enabled in raspi-config")
        sys.exit(1)

    # Test CameraController API directly
    print(format_section("Testing CameraController API"))

    try:
        # Test 1: Initialize CameraController with default settings
        print("\nTest 1: Initializing CameraController")
        camera = CameraController()
        print("✓ CameraController initialized")

        # Test 2: Initialize with custom configuration
        print("\nTest 2: Initializing CameraController with custom configuration")
        camera.initialize([1280, 720], vertical_flip=True, horizontal_flip=False)
        print("✓ CameraController configured with custom resolution and flips")

        # Test 3: Capture photo with default temp path
        print("\nTest 3: Capturing photo via CameraController (default temp path)")
        temp_photo_path = camera.capture()
        print(f"Photo saved to: {temp_photo_path}")

        assert os.path.exists(temp_photo_path), "Photo file was not created at temp path"
        print("✓ PASS - Photo file created at temp path")

        # Test 4: Capture photo with specified path
        print("\nTest 4: Capturing photo via CameraController (specified path)")
        specified_path = "/tmp/tjbot-controller-test.jpg"
        specified_photo_path = camera.capture(specified_path)
        print(f"Photo saved to: {specified_photo_path}")

        assert os.path.exists(specified_photo_path), "Photo file was not created at specified path"
        assert specified_photo_path == specified_path, "Photo path does not match requested path"
        print("✓ PASS - Photo file created at specified path")

        # Test 5: Cleanup
        print("\nTest 5: Cleaning up resources")
        camera.cleanup()
        print("✓ CameraController cleaned up")

        print(format_title("Camera Test Complete"))
        print("Note: Check the captured images to verify quality and settings.")
        print("Photo paths have been displayed above.\n")

    except Exception as error:
        print(f"\n✗ Error during CameraController test: {error}")
        print("\nMake sure:")
        print("  1. You are running on a Raspberry Pi")
        print("  2. rpicam-still command-line tool is installed")
        print("     Install with: sudo apt-get install rpicam-apps-lite")
        print("  3. Camera hardware is properly connected")
        print("  4. Camera interface is enabled in raspi-config")
        sys.exit(1)


if __name__ == "__main__":
    run_test()

