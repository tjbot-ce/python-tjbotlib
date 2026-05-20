# Python TJBot Parity Tracker

This file tracks implementation parity against node-tjbotlib.

## Legend
- [x] Implemented
- [~] Partial
- [ ] Missing

## Core
- [~] TJBot lifecycle parity (singleton + explicit initialize + safe cleanup/reinitialize + process cleanup hooks for atexit/signals on main thread; deeper exit semantics parity still pending)
- [~] Async API equivalents (async wrappers and async initialize coverage added; full async internal stack pending)
- [~] Capability semantics (`see` introduced; old `look` kept for compatibility)

## Subsystems
- [x] Camera basic capture
- [x] LED basic control (common anode + neopixel)
- [x] Servo basic movement
- [x] Speaker playback
- [~] STT (backend dispatch implemented, config alignment improved; backend behavior parity still incomplete)
- [~] TTS (backend dispatch implemented, config alignment improved; backend behavior parity still incomplete)
- [~] Vision subsystem (architecture + driver/TJBot wiring implemented; cloud backends + local ONNX inference paths implemented; deeper behavioral parity/perf validation pending)
- [x] Microphone capture via arecord subprocess (pyalsaaudio removed)

## Utilities
- [~] Config loading parity (recipe config + backend enum/field coverage improved; confidence range validation parity added; broader schema/edge-case parity still pending)
- [~] Credentials loading parity (shared helpers added for Azure/Google/IBM path resolution and env loading)
- [~] Model registry parity (metadata registry + download/cache/extract + `get_local_models` wiring implemented; robustness parity with Node still pending)

## Recent Fixes
- [x] Camera command detection updated to support `rpicam-still` in addition to `libcamera-still`/`raspistill`
- [x] STT/TTS cloud backend initialization now fails fast on credential/runtime init errors (prevents false-positive live smoke outcomes)

## Tests
- [~] Core tests expanded (TJBot init/constants/config/credentials/model-registry/vision + ONNX/STT/TTS mocked boundary tests)
- [~] Core API contract tests (Node-style TJBot method coverage added; remaining edge-case matrices and live parity still pending)
- [~] Live tests parity (Python live vision/STT/TTS harnesses now mirror Node interactive backend+device selection patterns; Google/Azure STT, TTS, and Vision live runs are validated; local sherpa live rows still blocked by runtime mismatch)

## Current Baseline
- [x] Core test suite green: 144 passed
