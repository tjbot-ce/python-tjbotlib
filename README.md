# TJBot Library (Python)

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi Support](https://img.shields.io/badge/Raspberry%20Pi-3%2C%204%2C%205-red)](https://www.raspberrypi.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

> 🤖 Python library for programming TJBot recipes!

## What is TJBot?

[TJBot](http://ibm.biz/mytjbot) is an open-source robot created by IBM for learning how to program artificial intelligence applications. This library provides a simple, high-level interface to control TJBot running on a Raspberry Pi.

## What Can TJBot Do?

TJBot's core capabilities are:

- **Listen** – Capture and transcribe speech with Speech-to-Text
- **See** – Take photos and analyze vision with an integrated camera (supports local ONNX backends for object detection, classification, and face detection)
- **Shine** – Control an RGB LED in various colors and effects
- **Speak** – Play audio and synthesize speech with Text-to-Speech
- **Wave** – Move its arm using a servo motor

This library supports both **local AI backends** (using sherpa-onnx for offline speech processing and ONNX Runtime for vision tasks) and **IBM Watson cloud services** for more advanced capabilities.

## System Dependencies

Install required system packages:

```bash
sudo apt-get update
sudo apt-get install -y rpicam-apps-lite libasound2-dev
```

> Note: `rpicam-apps-lite` is installed as part of TJBot's setup script.
> `libasound2-dev` is needed to build `pyalsaaudio` when syncing dependencies.

## Installation

Install the library using `pip`:

```bash
pip install python-tjbotlib
```

## Quick Start

### Importing TJBot

```python
from tjbot import TJBot
```

> **Note**: TJBot uses a singleton pattern. You can create an instance directly with `TJBot()` (recommended for simple use cases) or access the global instance with `TJBot.get_instance()` (useful for multi-module applications). The constructor defaults to `auto_initialize=True`, which will load configuration and initialize hardware immediately.

### Example 1: Control an LED

This example initializes a NeoPixel LED and sets its color:

```python
from tjbot import TJBot

# Initialize with NeoPixel LED enabled via override config
config = {
    "hardware": {
        "led": True
    },
    "shine": {
        "hasNeopixelLED": True,
        "neopixel": {
            "gpioPin": 18  # or your LED's GPIO pin
        }
    }
}
tj = TJBot(override_config=config)

# Set LED to red
tj.shine('red')

# Set LED to a custom hex color
tj.shine('#00FF00')

# Pulse the LED
tj.pulse('blue')

print('LED demo complete!')
```

### Example 2: Speak Text Using On-Device Text-to-Speech (TTS)

This example uses the `sherpa-onnx` text-to-speech backend to speak text:

```python
from tjbot import TJBot

# Initialize with speaker enabled
config = {
    "hardware": {
        "speaker": True
    },
    "speak": {
        "backend": {"type": "local"}
    }
}
tj = TJBot(override_config=config)

# Speak text using local TTS (sherpa-onnx)
# The TTS model is automatically downloaded on first use
tj.speak('Hello, I am TJBot!')

print('Speech demo complete!')
```

### Example 3: Change TJBot's Configuration

TJBot loads configuration from multiple sources in this order of priority:
1. Default configuration (bundled with the library)
2. User configuration from `~/.tjbot/tjbot.toml` (your home directory)
3. Recipe configuration from `recipe.toml` (current working directory, if present)

Create a `~/.tjbot/tjbot.toml` file in your home directory to customize TJBot's behavior:

**~/.tjbot/tjbot.toml:**

```toml
[log]
level = 'debug'

[shine.neopixel]
gpioPin = 18
```

Then use it in your code:

```python
from tjbot import TJBot

# TJBot automatically loads from ~/.tjbot/tjbot.toml
# Assuming tjbot.toml enables hasNeopixelLED
tj = TJBot()

# Use the configured settings
tj.shine('cyan')
tj.speak('TJBot is ready!')
```

### Using `override_config` for Runtime Configuration

You can also pass configuration directly to the `TJBot()` constructor using the `override_config` parameter. This configuration **merges with** the cascaded defaults (not replaces them):

```python
from tjbot import TJBot

# Override specific settings at runtime
config = {
    "shine": {
        "hasNeopixelLED": True,
        "neopixel": {"gpioPin": 18}
    }
}
tj = TJBot(override_config=config)

# The final config is: defaults + ~/.tjbot/tjbot.toml + override_config
```

## Configuration Reference

TJBot uses [TOML](https://toml.io/en/) for configuration. User configuration is stored in `~/.tjbot/tjbot.toml` (your home directory). Recipe-specific overrides go in `recipe.toml` (current working directory, optional).

The shared canonical config assets live in `vendor/tjbot-config` (git submodule), matching `node-tjbotlib`:

- `vendor/tjbot-config/tjbot-config.schema.yaml`
- `vendor/tjbot-config/model-registry.yaml`
- `vendor/tjbot-config/tjbot.default.toml`

For packaging/runtime, these assets are synced into:

- `src/tjbot/config/schema/tjbot-config.schema.yaml`
- `src/tjbot/config/model-registry.yaml`
- `src/tjbot/config/tjbot.default.toml`

Run the sync command after updating the submodule:

```bash
python3 scripts/sync_config_schema.py
```

## API Documentation

For detailed API documentation, please refer to the source code or generated docs.

## Development

### Setting Up a Development Environment

To contribute to the TJBot library:

1. **Clone the repository:**

   ```bash
    git clone --recurse-submodules https://github.com/ibmtjbot/python-tjbotlib.git
   cd python-tjbotlib
   ```

    If you already cloned without submodules:

    ```bash
    git submodule update --init --recursive
    ```

    This initializes shared configuration assets at `vendor/tjbot-config`.

2. **Install dependencies with uv:**

   ```bash
    uv sync
   ```

3. **Run tests:**

   ```bash
    uv run pytest
   ```

4. **Lint and format code:**

   ```bash
    uv run ruff check .
    uv run ruff format .
   ```

### uv Quick Reference

```bash
# ensure project Python version (see .python-version)
uv python install 3.11

# sync default groups (includes dev via tool.uv.default-groups)
uv sync

# run commands inside the managed environment
uv run pytest
uv run mypy src

# add a runtime dependency
uv add <package>

# add a development-only dependency
uv add --group dev <package>
```

## License

This project is licensed under the [Apache License 2.0](LICENSE).
