import pytest
from tjbot.config import TJBotConfig
from tjbot.config.models import HardwareConfig

def test_default_config_loading():
    config = TJBotConfig()
    assert config.log.level == 'info'
    assert config.hardware is not None
    # Check that listen config exists and has reasonable defaults
    assert config.listen is not None
    assert config.listen.microphoneRate > 0

def test_override_config():
    overrides = {
        'log': {'level': 'debug'},
        'hardware': {'camera': True}
    }
    config = TJBotConfig(overrides)
    assert config.log.level == 'debug'
    assert config.hardware.camera is True
    assert config.hardware.servo is False # Default is false usually in test override context? Need to check default.toml

def test_nested_override():
    overrides = {
        'shine': {
            'neopixel': {
                'gpioPin': 10
            }
        }
    }
    config = TJBotConfig(overrides)
    # Check only changed value, others should remain default
    assert config.shine.neopixel is not None
    assert config.shine.neopixel.gpioPin == 10
