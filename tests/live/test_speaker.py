#!/usr/bin/env python3
"""
Interactive TJBot Speaker Hardware Test

This test validates speaker/audio playback functionality.
"""

import sys
import os
import re
import struct
import math
import subprocess
from typing import Dict, List, Optional

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

try:
    from .utils import (
        format_title,
        format_section,
        is_command_available,
        confirm_user,
        select_option,
    )
except ImportError:
    from utils import (
        format_title,
        format_section,
        is_command_available,
        confirm_user,
        select_option,
    )


def list_alsa_output_devices() -> List[Dict[str, str]]:
    try:
        output = subprocess.check_output(['aplay', '-l'], text=True, stderr=subprocess.STDOUT)
    except Exception:
        return []

    devices: List[Dict[str, str]] = []
    pattern = re.compile(r'card\s+(\d+):.*?\[(.+?)\].*device\s+(\d+):.*?\[(.+?)\]')
    for line in output.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        card, card_name, device, device_name = match.groups()
        value = f'plughw:{card},{device}'
        name = f'Card {card}: {card_name} (Device {device}: {device_name})'
        devices.append({'name': name, 'value': value})
    return devices


def prompt_device_choice() -> Optional[str]:
    devices = list_alsa_output_devices()
    if len(devices) == 0:
        print('ℹ️  No ALSA output devices found; using system default')
        return None
    if len(devices) == 1:
        print(f'ℹ️  Using single ALSA output device: {devices[0]["name"]}')
        return devices[0]['value']
    return select_option('Select audio output device:', devices, default=devices[0]['value'])


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

    device = prompt_device_choice()

    # Import here to avoid import errors if dependencies missing
    from tjbot.speaker import SpeakerController

    # Create audio player directly to test playback
    speaker = SpeakerController()
    speaker.initialize(device or '')
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

        # Clean up test audio file
        try:
            os.unlink(test_audio_path)
            print("✓ Test audio file cleaned up")
        except Exception as err:
            print(f"Warning: Could not delete test audio file: {err}")

        print(format_title("Speaker Test Complete"))

    except Exception as error:
        print(f"\n✗ Error during speaker test: {error}")
        sys.exit(1)


if __name__ == "__main__":
    run_test()

