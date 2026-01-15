#!/usr/bin/env python3
"""
Interactive TJBot Speaker Hardware Test

This test validates speaker/audio playback functionality.
"""

import sys
import os
import struct
import math

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

try:
    from .utils import (
        format_title,
        format_section,
        is_command_available,
        confirm_user,
    )
except ImportError:
    from utils import (
        format_title,
        format_section,
        is_command_available,
        confirm_user,
    )


def generate_test_wav(path: str, frequency: int = 440, duration: float = 1.0) -> None:
    """
    Generate a simple WAV file with an audible tone

    Args:
        path: Output file path
        frequency: Tone frequency in Hz (default 440 Hz = A4 note)
        duration: Duration in seconds
    """
    sample_rate = 22050
    num_samples = int(sample_rate * duration)
    channels = 1
    bytes_per_sample = 2

    # WAV header
    header = bytearray(44)
    header[0:4] = b'RIFF'
    struct.pack_into('<I', header, 4, 36 + num_samples * bytes_per_sample)
    header[8:12] = b'WAVE'
    header[12:16] = b'fmt '
    struct.pack_into('<I', header, 16, 16)  # Subchunk1Size
    struct.pack_into('<H', header, 20, 1)   # AudioFormat (PCM)
    struct.pack_into('<H', header, 22, channels)
    struct.pack_into('<I', header, 24, sample_rate)
    struct.pack_into('<I', header, 28, sample_rate * bytes_per_sample)
    struct.pack_into('<H', header, 32, bytes_per_sample)
    struct.pack_into('<H', header, 34, bytes_per_sample * 8)
    header[36:40] = b'data'
    struct.pack_into('<I', header, 40, num_samples * bytes_per_sample)

    # Generate audio data - 440 Hz sine wave
    audio_data = bytearray(num_samples * bytes_per_sample)
    for i in range(num_samples):
        sample = math.sin((2 * math.pi * frequency * i) / sample_rate) * 32767 * 0.5
        struct.pack_into('<h', audio_data, i * 2, int(sample))

    with open(path, 'wb') as f:
        f.write(header)
        f.write(audio_data)


def run_test():
    """Run interactive speaker test"""
    print(format_title("TJBot Speaker Hardware Test"))

    # Check for required dependencies
    print("Checking for required dependencies...")

    if is_command_available("aplay"):
        print("✓ aplay command available")
    else:
        print("✗ aplay command not available")
        print("\nInstall with:")
        print("  sudo apt-get install alsa-utils\n")
        sys.exit(1)

    print("✓ All dependencies available\n")

    print(format_section("Testing TJBot speaker"))

    # Import here to avoid import errors if dependencies missing
    from tjbot.speaker import SpeakerController

    # Create audio player directly to test playback
    speaker = SpeakerController()
    speaker.initialize()
    print("✓ Speaker initialized\n")

    try:
        # Test 1: Generate test audio file and play
        print("Test 1: Playing a test audio file")
        test_audio_path = "/tmp/tjbot-test-beep.wav"

        print("Generating test audio file...")
        generate_test_wav(test_audio_path)

        print(f"Playing test audio: {test_audio_path}")
        speaker.play_audio(test_audio_path)

        result = confirm_user("Did you hear audio playback? (yes/no): ")
        print("✓ PASS" if result else "✗ FAIL")

        print(format_title("Speaker Test Complete"))

    except Exception as error:
        print(f"\n✗ Error during speaker test: {error}")
        sys.exit(1)


if __name__ == "__main__":
    run_test()

