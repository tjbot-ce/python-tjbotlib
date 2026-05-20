# TJBot Python Live Validation Matrix

This matrix tracks end-to-end live parity validation against node-tjbotlib interactive harness behavior.

## Scope

- STT live harness: `tests/live/test_stt.py`
- TTS live harness: `tests/live/test_tts.py`
- Vision live harness: `tests/live/test_vision.py`
- Camera, microphone, speaker, LED, servo hardware harnesses under `tests/live/`

## Environment Prerequisites

- Raspberry Pi (Pi 4 or Pi 5 recommended)
- Camera attached and enabled
- Microphone available via ALSA
- Speaker/output device available via ALSA
- Commands available:
  - `rpicam-still`
  - `arecord`
  - `aplay`
- Python dependencies installed with uv project sync
- Optional cloud credentials configured for backend-specific tests

## Current Host Quick Check (2026-05-15)

- `rpicam-still`: available
- `arecord`: available
- `aplay`: available
- ALSA capture devices detected: yes (USB PnP devices present)
- ALSA playback devices detected: yes (HDMI and USB playback devices present)

This means local live harness execution is not blocked by missing CLI audio/camera tools on this host.

## Runtime Module Check (2026-05-15)

- `numpy`: available
- `Pillow` (`PIL`): available
- `onnxruntime`: available
- `sherpa_onnx`: import fails on this host due runtime loader mismatch with external `LD_LIBRARY_PATH`

Additional detail from targeted runtime checks:

- with `LD_LIBRARY_PATH=''`: import fails with `libonnxruntime.so: cannot open shared object file`
- with `LD_LIBRARY_PATH=<venv>/site-packages/onnxruntime/capi`: import fails with `VERS_1.24.4 not found`
- with external `/home/pi/.tjbot/sherpa-onnx-linux-arm64` in `LD_LIBRARY_PATH`: import also fails with incompatible `libonnxruntime.so` symbol/version

## Status Key

- `PASS`: validated successfully in live run
- `FAIL`: validated and failed
- `SKIP`: not run due to missing hardware/credentials
- `PENDING`: not yet executed

## STT Matrix

| Backend | Device Select | Model/Voice Select | Partial/Final Behavior | Credentials | Status | Notes |
|---|---|---|---|---|---|---|
| local | yes | model | final transcript loop | n/a | FAIL | Script executes; local STT blocked by sherpa runtime loader mismatch (`LD_LIBRARY_PATH` points to incompatible `/home/pi/.tjbot/sherpa-onnx-linux-arm64` libs) |
| ibm-watson-stt | yes | model | final transcript loop | IBM | PENDING | Validate with env and file-based credentials |
| google-cloud-stt | yes | language+model | final transcript loop | GCP | PASS | Smoke run initialized successfully with `GOOGLE_APPLICATION_CREDENTIALS=/home/pi/.tjbot/google-credentials.json` |
| azure-stt | yes | language | final transcript loop | Azure | PASS | Smoke run initialized successfully after sourcing `/home/pi/.tjbot/azure-credentials.env` |

## TTS Matrix

| Backend | Output Device Select | Model/Voice Select | Playback | Credentials | Status | Notes |
|---|---|---|---|---|---|---|
| local | yes | model | yes | n/a | FAIL | Script executes; local TTS blocked by sherpa runtime loader mismatch (`LD_LIBRARY_PATH` points to incompatible `/home/pi/.tjbot/sherpa-onnx-linux-arm64` libs) |
| ibm-watson-tts | yes | voice | yes | IBM | PENDING | Validate long and short utterances |
| google-cloud-tts | yes | voice | yes | GCP | PASS | Smoke run synthesized and played successfully with `GOOGLE_APPLICATION_CREDENTIALS=/home/pi/.tjbot/google-credentials.json` using USB output device `plughw:3,0` |
| azure-tts | yes | voice | yes | Azure | PASS | Smoke run synthesized and played successfully after sourcing `/home/pi/.tjbot/azure-credentials.env` using USB output device `plughw:3,0` |

## Vision Matrix

| Backend | Task Select | Task Coverage | Capture | Annotation | Credentials | Status | Notes |
|---|---|---|---|---|---|---|---|
| local | yes | detect objects, classify, faces | yes | optional | n/a | PASS | Local classify-image path executed end-to-end; capture + ONNX inference completed (result may be empty depending on scene/model confidence) |
| google-cloud-vision | yes | detect objects, classify, faces | yes | yes for detect/faces | GCP | PASS | Vision smoke run completed end-to-end with `GOOGLE_APPLICATION_CREDENTIALS=/home/pi/.tjbot/google-credentials.json` (result may be empty for scene) |
| azure-vision | yes | detect objects, classify, describe image | yes | yes for detect path | Azure | PASS | Vision smoke run completed end-to-end after sourcing `/home/pi/.tjbot/azure-credentials.env`; face detection is intentionally unsupported |

## Hardware Harness Matrix

| Harness | Prerequisite | Core Behavior | Status | Notes |
|---|---|---|---|---|
| test_camera.py | rpicam-still | capture default/custom paths | PENDING | Validate multiple captures |
| test_microphone.py | arecord | records audio chunks | PENDING | Confirm non-trivial recorded bytes |
| test_speaker.py | aplay | plays generated tone | PENDING | Human-audible confirmation needed |
| test_led.py | LED wiring | color render/pattern | PENDING | Verify both common-anode and neopixel paths |
| test_servo.py | servo wiring | movement patterns | PENDING | Verify bounds and movement behavior |

## Execution Order

1. Run camera/microphone/speaker harnesses to validate base hardware.
2. Run local STT/TTS/Vision backends first.
3. Run cloud backends with credentials loaded.
4. Record results in this file (`PASS`/`FAIL`/`SKIP`) with notes.

## Logging and Evidence

For each backend run, capture:

- exact script used
- selected backend and model/voice
- command/tool dependencies found
- final outcome and any stack traces
- output artifacts (captured image paths, annotated image paths, sample transcript lines)
