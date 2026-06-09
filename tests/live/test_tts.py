#!/usr/bin/env python3

# Copyright 2026-present TJBot Contributors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Interactive TJBot Text-to-Speech (TTS) Test."""

import sys
import os
import re
import signal
import subprocess
from typing import Any, Dict, List, Optional

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))

from tjbot import TJBot
from tjbot.utils import ModelRegistry
from tjbot.utils.sherpa_runtime import load_sherpa_onnx_module

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
    "RESET": "\033[0m",
    "BRIGHT": "\033[1m",
    "GREEN": "\033[32m",
    "YELLOW": "\033[33m",
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

    selected_backend = prompt_backend_choice()
    if selected_backend == "local":
        verify_local_sherpa_runtime()
    backend_config = prompt_backend_specific_options(selected_backend)
    selected_output_device = prompt_output_device_choice()
    speak_config = build_speak_config(
        selected_backend, backend_config, selected_output_device
    )

    print(format_section(f"Initializing TJBot with TTS ({selected_backend})"))

    # Instantiate TJBot with override configuration
    tjbot = TJBot(
        {
            "log": {"level": "info"},
            "hardware": {
                "camera": False,
                "led_common_anode": False,
                "led_neopixel": False,
                "microphone": False,
                "servo": False,
                "speaker": True,
            },
            "speak": speak_config,
        }
    )

    print("✓ TJBot initialized")

    smoke_mode = os.getenv("TJBOT_LIVE_SMOKE") == "1"
    if smoke_mode:
        smoke_text = os.getenv("TJBOT_LIVE_SMOKE_TEXT", "TJBot live TTS smoke test")
        print(
            f"{COLORS['BRIGHT']}{COLORS['GREEN']}Speaking (smoke): {smoke_text}{COLORS['RESET']}"
        )
        tjbot.speak(smoke_text)
        print("✓ Smoke mode: one-shot synthesis complete")
        return

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
                    print(
                        f"{COLORS['BRIGHT']}{COLORS['GREEN']}Speaking: {text}{COLORS['RESET']}"
                    )
                    tjbot.speak(text)
                    print("")
            except KeyboardInterrupt:
                is_shutting_down = True
                break
            except Exception as error:
                if not is_shutting_down:
                    print(
                        f"{COLORS['YELLOW']}Error during synthesis: {error}{COLORS['RESET']}"
                    )
    except Exception as error:
        if not is_shutting_down:
            print(f"✗ TTS test failed: {error}")
            sys.exit(1)


def list_alsa_output_devices() -> List[Dict[str, str]]:
    try:
        output = subprocess.check_output(
            ["aplay", "-l"], text=True, stderr=subprocess.STDOUT
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


def prompt_output_device_choice() -> Optional[str]:
    devices = list_alsa_output_devices()
    if len(devices) == 0:
        print("ℹ️  No ALSA output devices found; using system default")
        return None
    if len(devices) == 1:
        print(f"ℹ️  Using single ALSA output device: {devices[0]['name']}")
        return devices[0]["value"]
    return select_option(
        "Select audio output device:", devices, default=devices[0]["value"]
    )


def prompt_backend_choice() -> str:
    return select_option(
        "Select a TTS backend to test:",
        [
            {"name": "Local (Sherpa ONNX)", "value": "local"},
            {"name": "IBM Watson", "value": "ibm-watson-tts"},
            {"name": "Google Cloud", "value": "google-cloud-tts"},
            {"name": "Azure", "value": "azure-tts"},
        ],
        default="local",
    )


def prompt_backend_specific_options(selected_backend: str) -> Dict[str, Any]:
    if selected_backend == "local":
        return prompt_sherpa_onnx_tts_options()
    if selected_backend == "ibm-watson-tts":
        return prompt_ibm_watson_tts_options()
    if selected_backend == "google-cloud-tts":
        return prompt_google_cloud_tts_options()
    if selected_backend == "azure-tts":
        return prompt_azure_tts_options()
    return {}


def prompt_sherpa_onnx_tts_options() -> Dict[str, Any]:
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models("tts", False)
    if not models:
        print("\nNo TTS models found in model registry; using backend defaults")
        return {}

    choices = []
    for model in models:
        downloaded = registry.is_model_downloaded(model.key)
        status = "✓ downloaded" if downloaded else "✗ not downloaded"
        choices.append(
            {"name": f"{model.label or model.key} {status}", "value": model.key}
        )

    model_key = select_option(
        "Select a Sherpa-ONNX TTS model:", choices, default=models[0].key
    )
    return {"model": model_key}


def prompt_ibm_watson_tts_options() -> Dict[str, Any]:
    voice = select_option(
        message="Select IBM Watson voice:",
        choices=[
            # Enhanced neural voices
            {"name": "Allison (US, Female, Enhanced)", "value": "en-US_AllisonV3Voice"},
            {"name": "Emily (US, Female, Enhanced)", "value": "en-US_EmilyV3Voice"},
            {"name": "Henry (US, Male, Enhanced)", "value": "en-US_HenryV3Voice"},
            {"name": "Kevin (US, Male, Enhanced)", "value": "en-US_KevinV3Voice"},
            {"name": "Lisa (US, Female, Enhanced)", "value": "en-US_LisaV3Voice"},
            {"name": "Michael (US, Male, Enhanced)", "value": "en-US_MichaelV3Voice"},
            {"name": "Olivia (US, Female, Enhanced)", "value": "en-US_OliviaV3Voice"},
            # Expressive neural voices
            {
                "name": "Allison (US, Female, Expressive)",
                "value": "en-US_AllisonExpressive",
            },
            {"name": "Emma (US, Female, Expressive)", "value": "en-US_EmmaExpressive"},
            {"name": "Lisa (US, Female, Expressive)", "value": "en-US_LisaExpressive"},
            {
                "name": "Michael (US, Male, Expressive)",
                "value": "en-US_MichaelExpressive",
            },
            # Natural voices
            {"name": "Ellie (US, Female, Natural)", "value": "en-US_EllieNatural"},
            {"name": "Emma (US, Female, Natural)", "value": "en-US_EmmaNatural"},
            {"name": "Ethan (US, Male, Natural)", "value": "en-US_EthanNatural"},
            {"name": "Jackson (US, Male, Natural)", "value": "en-US_JacksonNatural"},
            {
                "name": "Victoria (US, Female, Natural)",
                "value": "en-US_VictoriaNatural",
            },
        ],
        default="en-US_AllisonV3Voice",
    )
    return {"voice": voice}


def prompt_google_cloud_tts_options() -> Dict[str, Any]:
    voice = select_option(
        message="Select Google Cloud voice:",
        choices=[
            {"name": "en-US-Neural2-A (US, Male)", "value": "en-US-Neural2-A"},
            {"name": "en-US-Neural2-C (US, Female)", "value": "en-US-Neural2-C"},
            {"name": "en-US-Neural2-D (US, Male)", "value": "en-US-Neural2-D"},
            {"name": "en-US-Neural2-E (US, Female)", "value": "en-US-Neural2-E"},
            {"name": "en-US-Neural2-F (US, Female)", "value": "en-US-Neural2-F"},
            {"name": "en-US-Neural2-G (US, Female)", "value": "en-US-Neural2-G"},
            {"name": "en-US-Neural2-H (US, Female)", "value": "en-US-Neural2-H"},
            {"name": "en-US-Neural2-I (US, Male)", "value": "en-US-Neural2-I"},
            {"name": "en-US-Neural2-J (US, Male)", "value": "en-US-Neural2-J"},
            {"name": "en-US-Studio-O (US, Female)", "value": "en-US-Studio-O"},
            {"name": "en-US-Studio-Q (US, Male)", "value": "en-US-Studio-Q"},
        ],
        default="en-US-Neural2-A",
    )
    return {"voice": voice}


def prompt_azure_tts_options() -> Dict[str, Any]:
    voice_name = select_option(
        message="Select Azure voice:",
        choices=[
            {"name": "Amber (US, Female)", "value": "en-US-AmberNeural"},
            {"name": "Andrew (US, Male)", "value": "en-US-AndrewNeural"},
            {"name": "Aria (US, Female)", "value": "en-US-AriaNeural"},
            {"name": "Ashley (US, Female)", "value": "en-US-AshleyNeural"},
            {"name": "Ava (US, Female)", "value": "en-US-AvaNeural"},
            {"name": "Brian (US, Male)", "value": "en-US-BrianNeural"},
            {"name": "Davis (US, Male)", "value": "en-US-DavisNeural"},
            {"name": "Emma (US, Female)", "value": "en-US-EmmaNeural"},
            {"name": "Guy (US, Male)", "value": "en-US-GuyNeural"},
            {"name": "Jenny (US, Female)", "value": "en-US-JennyNeural"},
            {"name": "Roger (US, Male)", "value": "en-US-RogerNeural"},
            {"name": "Ryan (US, Male)", "value": "en-US-RyanNeural"},
            {"name": "Steffan (US, Male)", "value": "en-US-SteffanNeural"},
            {"name": "Zira (US, Female)", "value": "en-US-ZiraNeural"},
        ],
        default="en-US-AmberNeural",
    )
    return {"voiceName": voice_name}


def build_speak_config(
    selected_backend: str,
    backend_config: Dict[str, Any],
    selected_output_device: Optional[str],
) -> Dict[str, Any]:
    speak_config: Dict[str, Any] = {
        "backend": {
            "type": selected_backend,
        }
    }

    if selected_output_device:
        speak_config["device"] = selected_output_device

    if selected_backend == "local":
        speak_config["backend"]["local"] = backend_config
    elif selected_backend == "ibm-watson-tts":
        speak_config["backend"]["ibm-watson-tts"] = backend_config
    elif selected_backend == "google-cloud-tts":
        speak_config["backend"]["google-cloud-tts"] = backend_config
    elif selected_backend == "azure-tts":
        speak_config["backend"]["azure-tts"] = backend_config

    return speak_config


def verify_local_sherpa_runtime() -> None:
    try:
        load_sherpa_onnx_module()
    except Exception as error:
        print("✗ Local TTS backend requires a working sherpa_onnx runtime")
        print(f"  Import error: {error}")
        ld_library_path = os.getenv("LD_LIBRARY_PATH")
        if ld_library_path:
            print(f"  LD_LIBRARY_PATH={ld_library_path}")
            print(
                "  Hint: custom sherpa runtime libraries may be incompatible with installed package versions."
            )
        sys.exit(1)


if __name__ == "__main__":
    run_test()
