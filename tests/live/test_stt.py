#!/usr/bin/env python3
"""
Interactive TJBot Speech-to-Text (STT) Test

This test validates STT functionality with various backends.
Note: This is a simplified version. Cloud backends require credentials.
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
        prompt_input,
        select_option,
    )
except ImportError:
    from utils import (
        format_title,
        format_section,
        prompt_input,
        select_option,
    )

# ANSI color codes
COLORS = {
    'RESET': '\033[0m',
    'DIM': '\033[2m',
    'BRIGHT': '\033[1m',
    'GREEN': '\033[32m',
    'BLUE': '\033[34m',
    'YELLOW': '\033[33m',
}


def run_test():
    """Run interactive STT test"""
    print(format_title("TJBot STT Test"))

    # Get backend choice
    selected_backend = select_option(
        "Select STT backend",
        [
            {"name": "Local (Sherpa-ONNX)", "value": "local"},
            {"name": "IBM Watson", "value": "ibm-watson-stt"},
            {"name": "Google Cloud", "value": "google-cloud-stt"},
            {"name": "Azure", "value": "azure-stt"},
        ],
        default="local"
    )

    # Build listen config
    listen_config = {
        "backend": {
            "type": selected_backend
        }
    }

    print(format_section(f"Initializing TJBot with STT ({selected_backend})"))

    # Instantiate TJBot with override configuration
    tjbot = TJBot({
        "log": {"level": "info"},
        "hardware": {"microphone": True},
        "listen": listen_config
    })

    print("✓ TJBot initialized")

    print(format_section("Interactive test"))
    print("Start speaking. Press Ctrl+C when you are finished with the test.")

    last_partial = ""

    def on_partial_result(text):
        nonlocal last_partial
        if text and text != last_partial:
            last_partial = text
            print(f"{COLORS['DIM']}Partial: {text}{COLORS['RESET']}")

    def on_final_result(text):
        if text:
            print(f"{COLORS['BRIGHT']}{COLORS['GREEN']}Final: {text}{COLORS['RESET']}")

    # Main loop: continuously listen until user presses Ctrl+C
    is_shutting_down = False

    def handle_sigint(signum, frame):
        nonlocal is_shutting_down
        if not is_shutting_down:
            is_shutting_down = True
            print(f"\n{COLORS['YELLOW']}Shutting down...{COLORS['RESET']}")
            sys.exit(0)

    import signal
    signal.signal(signal.SIGINT, handle_sigint)

    try:
        while not is_shutting_down:
            try:
                # Note: Python implementation may differ from Node.js
                # This is a placeholder for the actual listen implementation
                transcript = tjbot.listen()
                if transcript:
                    print(f"{COLORS['BRIGHT']}{COLORS['GREEN']}Final: {transcript}{COLORS['RESET']}")
                last_partial = ""
            except Exception as error:
                if not is_shutting_down:
                    print(f"{COLORS['YELLOW']}Error during transcription: {error}{COLORS['RESET']}")
                    is_shutting_down = True
                    sys.exit(1)
    except Exception as error:
        if not is_shutting_down:
            print(f"✗ STT test failed: {error}")
            sys.exit(1)


if __name__ == "__main__":
    run_test()

