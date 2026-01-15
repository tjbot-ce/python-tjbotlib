#!/usr/bin/env python3
"""
Interactive TJBot Text-to-Speech (TTS) Test

This test validates TTS functionality with various backends.
Note: This is a simplified version. Cloud backends require credentials.
"""

import sys
import os
import signal

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

from tjbot import TJBot

try:
    from .utils import (
        format_title,
        format_section,
        prompt_input,
        is_command_available,
        select_option,
    )
except ImportError:
    from utils import (
        format_title,
        format_section,
        prompt_input,
        is_command_available,
        select_option,
    )

# ANSI color codes
COLORS = {
    'RESET': '\033[0m',
    'BRIGHT': '\033[1m',
    'GREEN': '\033[32m',
    'YELLOW': '\033[33m',
}


def run_test():
    """Run interactive TTS test"""
    print(format_title("TJBot TTS Test"))

    # Check for required dependencies
    print(format_section("Checking audio playback tools"))
    if not is_command_available("aplay"):
        print("✗ aplay command not available (required for audio playback)")
        print("\nInstall with:")
        print("  sudo apt-get install alsa-utils\n")
        sys.exit(1)
    print("✓ aplay command available\n")

    # Get backend choice
    selected_backend = select_option(
        "Select TTS backend",
        [
            {"name": "Local (Sherpa ONNX)", "value": "local"},
            {"name": "IBM Watson", "value": "ibm-watson-tts"},
            {"name": "Google Cloud", "value": "google-cloud-tts"},
            {"name": "Azure", "value": "azure-tts"},
        ],
        default="local"
    )

    # Build speak config
    speak_config = {
        "backend": {
            "type": selected_backend
        }
    }

    print(format_section(f"Initializing TJBot with TTS ({selected_backend})"))

    # Instantiate TJBot with override configuration
    tjbot = TJBot({
        "log": {"level": "info"},
        "hardware": {"speaker": True},
        "speak": speak_config
    })

    print("✓ TJBot initialized")

    print(format_section("Interactive test"))
    print("Enter text to speak. Press Ctrl+C to finish the test.")

    # Main loop: continuously synthesize until user presses Ctrl+C
    is_shutting_down = False

    def handle_sigint(signum, frame):
        nonlocal is_shutting_down
        if not is_shutting_down:
            is_shutting_down = True
            print(f"\n{COLORS['YELLOW']}Shutting down...{COLORS['RESET']}")
            sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        while not is_shutting_down:
            try:
                # Prompt user for text to synthesize
                text = prompt_input("\nEnter text to speak (or Ctrl+C to exit)")

                if text:
                    print(f"{COLORS['BRIGHT']}{COLORS['GREEN']}Speaking: {text}{COLORS['RESET']}")
                    tjbot.speak(text)
                    print("")
            except KeyboardInterrupt:
                is_shutting_down = True
                break
            except Exception as error:
                if not is_shutting_down:
                    print(f"{COLORS['YELLOW']}Error during synthesis: {error}{COLORS['RESET']}")
    except Exception as error:
        if not is_shutting_down:
            print(f"✗ TTS test failed: {error}")
            sys.exit(1)


if __name__ == "__main__":
    run_test()

