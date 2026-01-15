#!/usr/bin/env python3
"""
Interactive TJBot Microphone Hardware Test

This test validates microphone/audio capture functionality.
"""

import sys
import os
import time
import tempfile

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

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
    """Run interactive microphone test"""
    print(format_title("TJBot Microphone Hardware Test"))

    # Check for required dependencies
    print("Checking for required dependencies...")

    if is_command_available("arecord"):
        print("✓ arecord command available")
    else:
        print("✗ arecord command not available")
        print("\nInstall with:")
        print("  sudo apt-get install alsa-utils\n")
        sys.exit(1)

    print("✓ All dependencies available\n")

    print(format_section("Testing TJBot microphone"))

    # Import here to avoid import errors if dependencies missing
    from tjbot.microphone import MicrophoneController

    # Create and initialize microphone controller directly
    microphone = MicrophoneController()
    rate = 44100
    channels = 2
    # Auto-detect device (or could pass a specific device like 'plughw:2,0')
    microphone.initialize(rate, channels)

    print("✓ Microphone initialized\n")

    try:
        # Record audio to file and verify data was written
        print("Recording 5 seconds of audio to verify data capture...\n")
        temp_dir = tempfile.gettempdir()
        audio_file = os.path.join(temp_dir, f"tjbot_test_{int(time.time())}.raw")
        print(f"Recording to: {audio_file}")

        # Start microphone
        microphone.start()

        # Get the microphone input stream
        mic_stream = microphone.get_input_stream()

        print("Recording... Please make some noise (speak, clap, etc.)")

        # Collect audio data for 5 seconds
        audio_data = []
        start_time = time.time()
        try:
            for chunk in mic_stream:
                audio_data.append(chunk)
                if time.time() - start_time >= 5.0:
                    break
        except KeyboardInterrupt:
            pass

        # Stop recording
        microphone.stop()

        # Write collected data to file
        with open(audio_file, 'wb') as f:
            for chunk in audio_data:
                f.write(chunk)

        print("Recording complete.\n")

        # Check if file exists and has data
        test_passed = False
        if os.path.exists(audio_file):
            stats = os.stat(audio_file)
            file_size_kb = stats.st_size / 1024
            print(f"✓ File created: {audio_file}")
            print(f"✓ File size: {file_size_kb:.2f} KB ({stats.st_size} bytes)")

            # For 5 seconds of audio at 44.1kHz, stereo, 16-bit, we expect roughly:
            # 44100 samples/sec * 2 bytes/sample * 2 channels * 5 seconds = 882,000 bytes
            # We'll check if we have at least 50KB to account for buffering variations
            if stats.st_size > 50000:
                print("✓ PASS - Audio data captured successfully")
                test_passed = True
            else:
                print(f"✗ FAIL - File size too small ({file_size_kb:.2f} KB), expected > 50 KB")
                print("This suggests the microphone may not be working correctly.")
        else:
            print(f"✗ FAIL - File was not created: {audio_file}")

        print(format_title("Microphone Test Complete"))

        if not test_passed:
            sys.exit(1)

    except Exception as error:
        print(f"\n✗ Error during microphone test: {error}")
        print("\nMake sure:")
        print("  1. You are running on a Raspberry Pi")
        print("  2. A microphone is connected (USB or via audio hat)")
        print("  3. ALSA is properly configured")
        print("  4. You can see your microphone with: arecord -l")
        sys.exit(1)


if __name__ == "__main__":
    run_test()

