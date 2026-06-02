# TJBot Library (Python)

[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-3B+-cc342d)](https://www.raspberrypi.org/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## What is TJBot?

[TJBot](https://tjbot-ce.github.io) is an open-source robot created by IBM for learning how to program artificial intelligence applications. This library provides a simple, high-level interface to control TJBot running on a Raspberry Pi.

## What Can TJBot Do?

TJBot's core capabilities are:

- **Listen** – Capture and transcribe speech with Speech-to-Text
- **See** – Recognize objects, faces, and image classes (and describe images with Azure Vision)
- **Shine** – Control an RGB LED in various colors and effects
- **Speak** – Play audio and synthesize speech with Text-to-Speech
- **Wave** – Move its arm using a servo motor

This library supports **local AI backends** ([sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) for speech, [ONNX
runtime](https://onnxruntime.ai) for vision) and **cloud services** for speech and vision, including IBM
Watson (speech), Google Cloud (speech + vision), and Microsoft Azure (speech +
vision).

## System Dependencies

Install additional system packages:

```bash
sudo apt-get install libgpiod-dev liblgpiod-dev rpicam-apps-lite
```

> [!TIP]
> These packages are installed as part of TJBot's setup script.

## Installation

Install the library using `pip`:

```bash
pip install tjbot
```

Or, using `uv`:

```bash
uv init
uv add tjbot
```

> [!TIP]
> The easiest way to create a new Python-based TJBot recipe is using the `tjbot` command: `tjbot create [recipe-name]`, which will automatically set up `python-tjbotlib` as a dependency.

## Quick Start

### Importing & Initializing TJBot

Import and instantiate the TJBot class in your recipe. This example initializes TJBot's LED and servo motor.

```py
from tjbot import TJBot

tj = TJBot.get_instance().initialize({
    "hardware": {
        "led": True,
        "servo": True
    }
})
```

In the Python SDK, the TJBot constructor will also return the singleton instance and initialize TJBot's hardware (when `auto_initialize=True`, which is the default behavior):

```py
from tjbot import TJBot

tj = TJBot({
    "hardware": {
        "led": True,
        "servo": True
    }
})
```

> [!NOTE] TJBot uses a singleton pattern since there is only a single TJBot.

### Example 1: Control an LED

This example initializes a NeoPixel LED on the GPIO 18 pin and sets it to various colors:

```py
from tjbot import TJBot

tj = TJBot({
    "hardware": {
        "led": True
    },
    "shine": {
        "hasNeopixelLED": True,
        "neopixel": {
            "gpioPin": 18
        }
    }
})

# Set LED to red
tj.shine('red')

# Set LED to green (using hexadecimal)
tj.shine('#00FF00')

# Pulse the LED blue
tj.pulse('blue')
```

### Example 2: Speak Text Using Text-to-Speech (TTS)

This example demonstrates how to make TJBot speak using on-device Text-to-Speech.

> [!NOTE]
> The text-to-speech backend used by TJBot is set in TJBot's configuration file, located at `~/.tjbot/tjbot.toml`. By default, TJBot uses the `sherpa-onnx` text-to-speech backend.

```python
from tjbot import TJBot

tj = TJBot({
    "hardware": {
        "speaker": True
    },
    "speak": {
        "backend": {"type": "local"}
    }
})

tj.speak('Hello, I am T J Bot!')
```

> [!IMPORTANT]
> Many Text-to-Speech models are not trained to pronounce "TJBot" the way it is written. Writing it out as "T J Bot" makes it easier for these models to pronounce it correctly.

### Example 3: Change TJBot's Configuration

TJBot uses a cascading configuration system that loads settings from multiple
sources in order of priority. First, default configuration settings are loaded from the `tjbot.default.toml` file that is bundled within `node-tjbotlib`. Next, user-specific configuration is loaded from your `~/.tjbot/tjbot.toml` configuration file. Finally, recipe-specific configuration is loaded from the `recipe.toml` file in your recipe's directory (if present).

**User configuration (`~/.tjbot/tjbot.toml`):**

This file contains configuration settings for the hardware components of your TJBot, such as which pins the LED and servo are connected to, which audio devices to use for recording & playback, and which STT/TTS/Vision backends to use. Example:

```toml
[log]
level = 'debug' # TJBot will print a lot of detail about its operations to the console

[shine.neopixel]
gpioPin = 18 # GPIO 18 / Physical Pin 12

...
```

> [!TIP]
> You can either use the `tjbot config` command to edit TJBot's configuration or you can edit the `~/.tjbot/tjbot.toml` file directly.

**Recipe-specific configuration (`recipe.toml`):**

This file contains configuration settings for your recipe. It is placed in
your project directory.

```toml
tjbot_name = "tinker"
favorite_color = "blue"
cloud_api_key = "xyzabc"
```

Recipe-specific settings are loaded using the `TJBot.get_recipe_config()` class method.

```py
from tjbot import TJBot

config = TJBot.get_recipe_config()

tj = TJBot({
   "hardware": {
      led: True
   }
})

favorite_color = config.get('favorite_color')
tj.shine(favorite_color)
```

### Using `override_config` for Runtime Configuration

You can also pass specific configuration requirements directly to the `TJBot()` constructor using the `override_config` parameter. This configuration **merges with** the cascaded defaults (not replaces them):

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

> [!TIP]
> You can use `override_config` to explicitly enable any specific hardware required for your recipe.

## Configuration Reference

TJBot uses [TOML](https://toml.io/en/) for its configuration. The canonical default configuration lives in [vendor/tjbot-config/tjbot.default.toml](vendor/tjbot-config/tjbot.default.toml) and follows the schema specified in [vendor/tjbot-config/tjbot-config.schema.yaml](vendor/tjbot-config/tjbot-config.schema.yaml).

These files are synced into [src/config/](src/config/) during builds. They can be synced manually by running this command:

```bash
mise run sync-config-schema
```

### Custom Models & Model Registry

TJBot ships with a built-in model registry in
[vendor/tjbot-config/model-registry.yaml](vendor/tjbot-config/model-registry.yaml). The registry is synced into [src/config/model-registry.yaml](src/config/model-registry.yaml) during builds for local development and packaging. You can register additional ML models in your `~/.tjbot/tjbot.toml` file. Search for the section titled "On-Device ML Models".

Example: register a custom vision classification model and use it locally:

```toml
[[models]]
type = 'vision.classification'
key = 'my-classifier'
label = 'My Classifier'
url = 'file:///home/pi/models/my-classifier.zip'
folder = 'my-classifier'
kind = 'classification'
required = ['model.onnx', 'labels.txt']
labelUrl = 'file:///home/pi/models/labels.txt'
inputShape = [1, 3, 224, 224]

[see.backend]
type = 'local'

[see.backend.local]
imageClassificationModel = 'my-classifier'
```

You can register custom speech models in the same way.

## API Documentation

For detailed API documentation, method signatures, and advanced usage, visit
the [TJBot Python SDK Reference](https://tjbot-ce.github.io/docs/python-tjbotlib/3.0.0/).

## Testing

The library uses [pytest](https://docs.pytest.org/en/stable/) for testing with two tiers of
tests:

### Automated Tests (Core Tests)

TJBot ships with a number of unit tests that verify the library's core functionality.

```bash
# Run all automated tests
mise run test

# Run tests with coverage report
mise run test-coverage
```

These tests run on a Raspberry Pi but do not require any specific TJBot
hardware.

> [!WARNING]
> TJBot's software has not been tested on operating systems or hardware
> other than Raspian OS on Raspberry Pi.

### Interactive Hardware Tests (Live Tests)

TJBot also ships with a number of interactive tests meant to test (and debug) your Raspberry Pi hardware setup. These tests validate each of these components:

```bash
# Test the camera
mise run test-camera

# Test the LED
mise run test-led

# Test the microphone
mise run test-microphone

# Test the servo
mise run test-servo

# Test the speaker
mise run test-speaker

# Test the STT service (allows you to choose which backend to use)
mise run test-stt

# Test the TTS service (allows you to choose which backend to use)
mise run test-tts

# Test the Vision service (allows you to choose which backend to use and which vision task to perform)
mise run test-vision
```

> [!WARNING]
> These tests must be run on a Raspberry Pi with properly connected hardware components.

## Development

To set up a local development environment, you will first need to check out `node-tjbotlib` from GitHub. Then you will create a new recipe and point it to your locally-checked out copy of `node-tjbotlib`.

### Clone `python-tjbotlib`

1. **Clone the repository:**

   ```bash
    git clone --recurse-submodules https://github.com/tjbot-ce/python-tjbotlib.git
    cd python-tjbotlib
    ```

    If you already cloned the repo without submodules, run:

    ```bash
    git submodule update --init --recursive
    ```

    This initializes the shared TJBot configuration assets submodule at `vendor/tjbot-config`.

2. **Install dependencies**

    ```bash
    uv sync
    ```

3. **Run tests**

    ```bash
    mise run test
    ```

4. **Lint and format code:**

    ```bash
    mise run format
    mise run lint
    ```

### Create a Recipe

Create a new recipe using `tjbot create <recipe>`, then link it to the local version of `python-tjbotlib`.

1. **Create a new recipe**

   ```bash
   tjbot create my_recipe
   ```

2. **Link the recipe to the local `python-tjbotlib`**

   ```bash
   cd my_recipe
   uv add --editable ~/.tjbot/python-tjbotlib
   ```

> [!NOTE]
> This example assumes you have checked out `python-tjbotlib` to your `~/.tjbot` folder.

## Troubleshoot

If you are having difficulties in making your TJBot work, please see the [troubleshooting guide](https://github.com/tjbot-ce/tjbot/wiki/Troubleshooting-TJBot).

## Contribute

If you would like to contribute to TJBot, please see the [contributor's guide](https://github.com/tjbot-ce/tjbot/wiki/Contributing-to-TJBot).

## License

This project is licensed under Apache 2.0. Full license text is available in [LICENSE](LICENSE).
