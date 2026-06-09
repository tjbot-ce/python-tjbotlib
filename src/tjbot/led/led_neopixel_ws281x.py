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

"""
NeoPixel root helper process.

This process is launched as root (via sudo) by LEDNeopixel to gain access to
rpi_ws281x, which requires root privileges on RPi 3/4.

Protocol: newline-delimited JSON on stdin/stdout.
  Requests:
    { "id": ..., "cmd": "init",     "pin": N, "numLeds": N }
    { "id": ..., "cmd": "render",   "color": N }  -- color is a 32-bit integer (0xRRGGBB)
    { "id": ..., "cmd": "reset" }
    { "id": ..., "cmd": "shutdown" }
  Responses:
    { "id": ..., "ok": true }
    { "id": ..., "ok": false, "error": "<message>" }

stderr is for human-readable diagnostics only and does not affect the protocol.
"""

import json
import signal
import sys

try:
    from rpi_ws281x import PixelStrip  # type: ignore
except ImportError:
    PixelStrip = None

LED_DMA = 10
LED_FREQ_HZ = 800000
LED_BRIGHTNESS = 255
LED_INVERT = False

initialized = False
strip = None


def reply(req_id, ok, error=None):
    if ok:
        msg = {"id": req_id, "ok": True}
    else:
        msg = {"id": req_id, "ok": False, "error": str(error or "unknown error")}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def handle(req):
    global initialized, strip

    req_id = req.get("id")
    cmd = req.get("cmd")

    try:
        if cmd == "init":
            pin = int(req.get("pin", 0))
            num_leds = int(req.get("numLeds", 1))
            if pin < 0 or pin > 40:
                reply(req_id, False, f"invalid pin: {pin}")
                return
            if PixelStrip is None:
                reply(req_id, False, "rpi_ws281x library not found. Please install it.")
                return
            strip = PixelStrip(
                num_leds, pin, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS
            )
            strip.begin()
            initialized = True
            reply(req_id, True)

        elif cmd == "render":
            if not initialized or strip is None:
                reply(req_id, False, "not initialized")
                return
            color = int(req.get("color", 0))
            if color < 0 or color > 0xFFFFFF:
                reply(req_id, False, f"invalid color: {color}")
                return
            strip.setPixelColor(0, color)
            strip.show()
            reply(req_id, True)

        elif cmd == "reset":
            if initialized and strip is not None:
                strip.setPixelColor(0, 0)
                strip.show()
            reply(req_id, True)

        elif cmd == "shutdown":
            if initialized and strip is not None:
                strip.setPixelColor(0, 0)
                strip.show()
                initialized = False
                strip = None
            reply(req_id, True)
            sys.stdout.flush()
            sys.exit(0)

        else:
            reply(req_id, False, f"unknown command: {cmd}")

    except Exception as e:
        reply(req_id, False, str(e))


def _cleanup_and_exit():
    global initialized, strip
    if initialized and strip is not None:
        try:
            strip.setPixelColor(0, 0)
            strip.show()
        except Exception:
            pass
    sys.exit(0)


def _handle_sigterm(signum, frame):
    _cleanup_and_exit()


signal.signal(signal.SIGTERM, _handle_sigterm)

# Read newline-delimited JSON from stdin
_buffer = ""

try:
    for _line in sys.stdin:
        _line = _line.strip()
        if not _line:
            continue
        try:
            _req = json.loads(_line)
            handle(_req)
        except json.JSONDecodeError:
            pass  # Malformed JSON — no id to reply to, silently ignore

except (EOFError, KeyboardInterrupt):
    pass

# stdin closed — clean up and exit
_cleanup_and_exit()
