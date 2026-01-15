import pytest
import unittest.mock as mock
from tjbot import TJBot
from tjbot.rpi_drivers import RPiCommonDriver

@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPiCommonDriver')
def test_tjbot_init_common_driver(MockDriver, MockDetect):
    # Mock RPiDetect to return Pi 4 (supported by CommonDriver)
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot()

    assert isinstance(bot, TJBot)
    MockDriver.assert_called_once()
    assert bot.rpi_model == "Raspberry Pi 4 Model B"

@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi5Driver')
def test_tjbot_init_pi5_driver(MockDriver, MockDetect):
    # Mock Pi 5
    MockDetect.model.return_value = "Raspberry Pi 5 Model B"
    MockDetect.is_pi5.return_value = True

    bot = TJBot()

    MockDriver.assert_called_once()
    assert bot.rpi_model == "Raspberry Pi 5 Model B"

@mock.patch('tjbot.tjbot.RPiDetect')
def test_tjbot_hardware_init(MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    # Configure with hardware dict (correct format)
    config = {
        'hardware': {
            'camera': False,
            'led_common_anode': True
        }
    }

    with mock.patch('tjbot.tjbot.RPiCommonDriver') as MockDriver:
        driver_instance = MockDriver.return_value
        bot = TJBot(config)

        # Just verify bot was created successfully
        assert isinstance(bot, TJBot)
