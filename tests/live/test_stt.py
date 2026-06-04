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

"""Interactive TJBot Speech-to-Text (STT) Test."""

import re
import signal
import subprocess
import sys
import os
import threading
from typing import Any, Dict, List, Optional

# Add parent directory to path for script execution
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))

from tjbot import TJBot
from tjbot.utils import ModelRegistry
from tjbot.utils.errors import TJBotError
from tjbot.utils.sherpa_runtime import load_sherpa_onnx_module

try:
    from .utils import (
        format_title,
        format_section,
        select_option,
        is_command_available,
    )
except ImportError:
    from utils import (
        format_title,
        format_section,
        select_option,
        is_command_available,
    )

# ANSI color codes
COLORS = {
    "RESET": "\033[0m",
    "DIM": "\033[2m",
    "BRIGHT": "\033[1m",
    "GREEN": "\033[32m",
    "BLUE": "\033[34m",
    "YELLOW": "\033[33m",
}


def run_test():
    """Run interactive STT test"""
    print(format_title("TJBot STT Test"))

    print(format_section("Checking audio capture tools"))
    if not is_command_available("arecord"):
        print("✗ arecord command not available (required for audio capture)")
        print("\nInstall with:")
        print("  sudo apt-get install alsa-utils\n")
        sys.exit(1)
    print("✓ arecord command available\n")

    # Get backend choice
    selected_backend = prompt_backend_choice()
    if selected_backend == "local":
        verify_local_sherpa_runtime()
    backend_config = prompt_backend_specific_options(selected_backend)
    selected_device = prompt_device_choice()
    listen_config = build_listen_config(
        selected_backend, backend_config, selected_device
    )

    print(format_section(f"Initializing TJBot with STT ({selected_backend})"))

    # Instantiate TJBot with override configuration
    tjbot = TJBot(
        {
            "log": {"level": "info"},
            "hardware": {
                "camera": False,
                "led_common_anode": False,
                "led_neopixel": False,
                "microphone": True,
                "servo": False,
                "speaker": False,
            },
            "listen": listen_config,
        }
    )

    print("✓ TJBot initialized")

    smoke_mode = os.getenv("TJBOT_LIVE_SMOKE") == "1"
    if smoke_mode:
        print("✓ Smoke mode: STT backend initialized; skipping continuous listen loop")
        return

    print(format_section("Interactive test"))
    print("Start speaking. Press Ctrl+C when you are finished with the test.")

    # Main loop: continuously listen until user presses Ctrl+C
    is_shutting_down = False
    shutdown_event = threading.Event()

    driver = getattr(tjbot, "rpi_driver", None)
    stt_controller = getattr(driver, "stt_controller", None) if driver else None
    if stt_controller is None:
        print("✗ STT controller is unavailable after TJBot initialization")
        sys.exit(1)

    def stop_live_microphone() -> None:
        stop_mic = getattr(driver, "stop_mic", None) if driver is not None else None
        if callable(stop_mic):
            try:
                stop_mic()
            except Exception:
                pass

    def handle_sigint(signum, frame):
        nonlocal is_shutting_down
        _ = signum, frame
        if not is_shutting_down:
            is_shutting_down = True
            shutdown_event.set()
            print(f"\n{COLORS['YELLOW']}Shutting down...{COLORS['RESET']}")
            stop_live_microphone()

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        while not is_shutting_down:
            try:
                transcript = stt_controller.transcribe(
                    abort_signal=shutdown_event
                ).strip()
                if is_shutting_down:
                    break
                if transcript:
                    print(
                        f"{COLORS['BRIGHT']}{COLORS['GREEN']}Final: {transcript}{COLORS['RESET']}"
                    )
            except TJBotError as error:
                if error.code == "stt.aborted" and is_shutting_down:
                    break
                raise
            except Exception as error:
                if not is_shutting_down:
                    print(
                        f"{COLORS['YELLOW']}Error during transcription: {error}{COLORS['RESET']}"
                    )
                    is_shutting_down = True
                    shutdown_event.set()
                    stop_live_microphone()
                    sys.exit(1)
    except KeyboardInterrupt:
        is_shutting_down = True
        shutdown_event.set()
        print(f"\n{COLORS['YELLOW']}Shutting down...{COLORS['RESET']}")
        stop_live_microphone()
    except TJBotError as error:
        if error.code == "stt.aborted" or is_shutting_down:
            pass  # Normal abort during shutdown
        else:
            print(f"✗ STT test failed: {error}")
            sys.exit(1)
    except Exception as error:
        if not is_shutting_down:
            print(f"✗ STT test failed: {error}")
            sys.exit(1)
    finally:
        shutdown_event.set()
        stop_live_microphone()


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


def prompt_backend_choice() -> str:
    return select_option(
        "Select an STT backend to test:",
        [
            {"name": "Local (Sherpa-ONNX)", "value": "local"},
            {"name": "IBM Watson", "value": "ibm-watson-stt"},
            {"name": "Google Cloud", "value": "google-cloud-stt"},
            {"name": "Azure", "value": "azure-stt"},
        ],
        default="local",
    )


def prompt_backend_specific_options(selected_backend: str) -> Dict[str, Any]:
    if selected_backend == "local":
        return prompt_sherpa_onnx_options()
    if selected_backend == "ibm-watson-stt":
        return prompt_ibm_watson_options()
    if selected_backend == "google-cloud-stt":
        return prompt_google_cloud_options()
    if selected_backend == "azure-stt":
        return prompt_azure_options()
    return {}


def prompt_sherpa_onnx_options() -> Dict[str, Any]:
    registry = ModelRegistry.get_instance()
    models = registry.lookup_models("stt", False)
    if not models:
        print("\nNo STT models found in model registry; using backend defaults")
        return {}

    choices = []
    for model in models:
        downloaded = registry.is_model_downloaded(model.key)
        status = "✓ downloaded" if downloaded else "✗ not downloaded"
        choices.append(
            {"name": f"{model.label or model.key} {status}", "value": model.key}
        )

    model_key = select_option(
        "Select a Sherpa-ONNX STT model:", choices, default=models[0].key
    )
    return {"model": model_key}


def prompt_ibm_watson_options() -> Dict[str, Any]:
    model = select_option(
        message="Select IBM Watson model:",
        choices=[
            {"name": "Multimedia (general audio)", "value": "en-US_Multimedia"},
            {"name": "Telephony (phone/VoIP)", "value": "en-US_Telephony"},
            {"name": "Broadband", "value": "en-US_BroadbandModel"},
            {"name": "Narrowband (8kHz)", "value": "en-US_ShortForm_NarrowbandModel"},
        ],
        default="en-US_Multimedia",
    )

    noiseLevel = select_option(
        message="Background audio suppression level (0=none, 1=max):",
        choices=[
            {"name": "None (0.0)", "value": 0.0},
            {"name": "Low (0.3)", "value": 0.3},
            {"name": "Medium (0.5)", "value": 0.5},
            {"name": "High (0.8)", "value": 0.8},
            {"name": "Maximum (1.0)", "value": 1.0},
        ],
        default=0.4,
    )

    return {
        "model": model,
        "backgroundAudioSuppression": noiseLevel,
    }


def prompt_google_cloud_options() -> Dict[str, Any]:
    supported_regions_by_model = {
        "chirp_3": [
            {"name": "US (multi-region)", "value": "us"},
            {"name": "EU (multi-region)", "value": "eu"},
        ],
        "chirp_2": [
            {"name": "US Central 1", "value": "us-central1"},
            {"name": "Europe West 4", "value": "europe-west4"},
            {"name": "Asia Southeast 1", "value": "asia-southeast1"},
        ],
    }

    language_code = select_option(
        "Select language:",
        [
            {"name": "English (US)", "value": "en-US"},
            {"name": "English (GB)", "value": "en-GB"},
            {"name": "Spanish (Spain)", "value": "es-ES"},
            {"name": "Spanish (Mexico)", "value": "es-MX"},
            {"name": "French (France)", "value": "fr-FR"},
            {"name": "German", "value": "de-DE"},
            {"name": "Chinese (Mandarin)", "value": "zh-CN"},
            {"name": "Japanese", "value": "ja-JP"},
            {"name": "Korean", "value": "ko-KR"},
        ],
        default="en-US",
    )

    model_type = select_option(
        "Select model type:",
        [
            {"name": "Chirp 3 (v2)", "value": "chirp_3"},
            {"name": "Chirp 2 (v2)", "value": "chirp_2"},
        ],
        default="chirp_3",
    )

    region_choices = supported_regions_by_model[model_type]
    region = select_option(
        "Select region:",
        region_choices,
        default=region_choices[0]["value"],
    )

    return {
        "languageCode": language_code,
        "model": model_type,
        "region": region,
    }


def prompt_azure_options() -> Dict[str, Any]:
    language = select_option(
        message="Select Azure language:",
        choices=[
            {"name": "English (US)", "value": "en-US"},
            {"name": "English (GB)", "value": "en-GB"},
            {"name": "Spanish (Spain)", "value": "es-ES"},
            {"name": "Spanish (Mexico)", "value": "es-MX"},
            {"name": "French (France)", "value": "fr-FR"},
            {"name": "German", "value": "de-DE"},
            {"name": "Chinese (Mandarin)", "value": "zh-CN"},
            {"name": "Japanese", "value": "ja-JP"},
            {"name": "Korean", "value": "ko-KR"},
        ],
        default="en-US",
    )
    return {"language": language}


def build_listen_config(
    selected_backend: str,
    backend_config: Dict[str, Any],
    selected_device: Optional[str],
) -> Dict[str, Any]:
    listen_config: Dict[str, Any] = {
        # Mirror node-tjbotlib live STT harness defaults for all backends.
        "microphoneRate": 16000,
        "microphoneChannels": 1,
        "backend": {
            "type": selected_backend,
        },
    }

    if selected_device:
        listen_config["device"] = selected_device

    if selected_backend == "local":
        listen_config["backend"]["local"] = backend_config
    elif selected_backend == "ibm-watson-stt":
        listen_config["backend"]["ibm-watson-stt"] = backend_config
    elif selected_backend == "google-cloud-stt":
        listen_config["backend"]["google-cloud-stt"] = backend_config
    elif selected_backend == "azure-stt":
        listen_config["backend"]["azure-stt"] = backend_config

    return listen_config


def verify_local_sherpa_runtime() -> None:
    try:
        load_sherpa_onnx_module()
    except Exception as error:
        print("✗ Local STT backend requires a working sherpa_onnx runtime")
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
