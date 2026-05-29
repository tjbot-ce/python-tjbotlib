#!/usr/bin/env python3
"""
Interactive TJBot Microphone Hardware Test

This test validates microphone/audio capture functionality.
"""

import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import wave
from typing import Dict, List, Optional

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))

try:
    from .utils import (
        format_title,
        format_section,
        is_command_available,
        select_option,
    )
except ImportError:
    from utils import (
        format_title,
        format_section,
        is_command_available,
        select_option,
    )

DURATION_S = 10
BAR_WIDTH = 40
# Gain applied before clamping to [0,1]. Typical USB mic RMS ~0.01–0.05;
# multiplying by 10 maps quiet speech to the lower third of the bar.
GAIN = 10


def compute_rms(data: bytes) -> float:
    """Compute RMS of a 16-bit signed little-endian PCM buffer, scaled to [0, 1]."""
    sample_count = len(data) // 2
    if sample_count == 0:
        return 0.0
    samples = struct.unpack_from(f"<{sample_count}h", data)
    sum_squares = sum(s * s for s in samples)
    return min((sum_squares / sample_count) ** 0.5 / 32768.0 * GAIN, 1.0)


def render_vu_meter(level: float, peak: float, seconds_left: int) -> None:
    """Overwrite the current terminal line with an ASCII VU meter."""
    filled = round(level * BAR_WIDTH)
    peak_pos = min(round(peak * BAR_WIDTH), BAR_WIDTH - 1)

    bar = ""
    for i in range(BAR_WIDTH):
        if i < filled:
            bar += "\u2588"  # █
        elif i == peak_pos and peak_pos >= filled:
            bar += "\u258c"  # ▌ peak-hold marker
        else:
            bar += "\u2591"  # ░

    pct = str(round(level * 100)).rjust(3)
    pk_pct = str(round(peak * 100)).rjust(3)
    sys.stdout.write(
        f"\r\u23f1  {str(seconds_left).rjust(2)}s \u2502 \U0001f3a4 [{bar}] {pct}% \u2502 peak: {pk_pct}%  "
    )
    sys.stdout.flush()


def list_alsa_input_devices() -> List[Dict[str, str]]:
    try:
        output = subprocess.check_output(
            ["arecord", "-l"], text=True, stderr=subprocess.STDOUT
        )
    except Exception:
        return []

    devices: List[Dict[str, str]] = []
    pattern = re.compile(r"card\s+(\d+):.*?\[(.+?)\].*device\s+(\d+):.*?\[(.+?)\]")
    for line in output.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        card, card_name, device, device_name = match.groups()
        value = f"plughw:{card},{device}"
        name = f"Card {card}: {card_name} (Device {device}: {device_name})"
        devices.append({"name": name, "value": value})
    return devices


def prompt_device_choice() -> Optional[str]:
    devices = list_alsa_input_devices()
    if len(devices) == 0:
        print("ℹ️  No ALSA input devices found; using system default")
        return None
    if len(devices) == 1:
        print(f"ℹ️  Using single ALSA input device: {devices[0]['name']}")
        return devices[0]["value"]
    return select_option(
        "Select audio input device:", devices, default=devices[0]["value"]
    )


def run_test():
    """Run interactive microphone test"""
    print(format_title("TJBot Microphone Hardware Test"))

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

    from tjbot.microphone import MicrophoneController

    selected_device = prompt_device_choice()

    microphone = MicrophoneController()
    rate = 44100
    channels = 2
    microphone.initialize(rate, channels, selected_device or "")

    print("✓ Microphone initialized\n")

    try:
        print(
            f"Recording {DURATION_S} seconds of audio. Make some noise (speak, clap, etc.)!\n"
        )
        audio_file = os.path.join(
            tempfile.gettempdir(), f"tjbot_test_{int(time.time())}.wav"
        )

        microphone.start()
        mic_stream = microphone.get_input_stream()

        chunks: List[bytes] = []
        peak = 0.0
        remaining = DURATION_S
        start_time = time.time()
        last_second = 0

        try:
            for chunk in mic_stream:
                chunks.append(chunk)

                elapsed = time.time() - start_time
                current_second = int(elapsed)
                if current_second != last_second:
                    remaining = max(0, DURATION_S - current_second)
                    last_second = current_second

                rms = compute_rms(chunk)
                peak = rms if rms > peak else peak * 0.95
                render_vu_meter(rms, peak, remaining)

                if elapsed >= DURATION_S:
                    break
        except KeyboardInterrupt:
            pass

        sys.stdout.write("\n")
        sys.stdout.flush()

        microphone.stop()

        with wave.open(audio_file, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(rate)
            for chunk in chunks:
                wf.writeframes(chunk)

        print("\nRecording complete.\n")

        test_passed = False
        if os.path.exists(audio_file):
            stats = os.stat(audio_file)
            file_size_kb = stats.st_size / 1024
            print(f"✓ File created: {audio_file}")
            print(f"✓ File size: {file_size_kb:.2f} KB ({stats.st_size} bytes)")

            if stats.st_size > 50000:
                print("✓ File contains substantial audio data")

                with open(audio_file, "rb") as f:
                    sample = f.read(min(1000, stats.st_size))

                if any(b != 0 for b in sample):
                    print("✓ File contains non-zero audio data (likely actual sound)")
                    test_passed = True
                else:
                    print("✗ File appears to contain only zeros (no audio data)")
            else:
                print(f"✗ File size too small ({file_size_kb:.2f} KB < 50 KB expected)")
        else:
            print("✗ File was not created")

        print("✓ PASS" if test_passed else "✗ FAIL")
        print(format_title("Microphone Test Complete"))

        if test_passed:
            print("Microphone is working correctly!\n")
        else:
            print("Microphone test failed. Possible causes:")
            print("  - No microphone connected")
            print("  - Microphone not set as default recording device")
            print("  - Check with: arecord -l")
            print("  - Test manually: arecord -d 5 test.wav && aplay test.wav\n")
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
