import pytest
import unittest.mock as mock
import asyncio
import signal
import threading
import time
from types import SimpleNamespace
from tjbot import TJBot
from tjbot.utils.errors import TJBotError
from tjbot.rpi_drivers import RPi4Driver

@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
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

    with mock.patch('tjbot.tjbot.RPi4Driver') as MockDriver:
        driver_instance = MockDriver.return_value
        bot = TJBot(config)

        # Just verify bot was created successfully
        assert isinstance(bot, TJBot)


def test_tjbot_led_neopixel_enabled_without_config_raises():
    bot = TJBot(auto_initialize=False)
    bot.rpi_driver = mock.MagicMock()
    bot.config = SimpleNamespace(
        hardware=SimpleNamespace(
            speaker=False,
            microphone=False,
            camera=False,
            led_neopixel=True,
            led_common_anode=False,
            servo=False,
        ),
        shine=SimpleNamespace(neopixel=SimpleNamespace(gpio_pin=None, spi_interface=None), common_anode=None),
        see=None,
        listen=None,
        wave=None,
        speak=None,
    )

    with pytest.raises(TJBotError, match='NeoPixel LED hardware is enabled'):
        bot._initialize_hardware_from_config()


def test_tjbot_led_common_anode_enabled_without_config_raises():
    bot = TJBot(auto_initialize=False)
    bot.rpi_driver = mock.MagicMock()
    bot.config = SimpleNamespace(
        hardware=SimpleNamespace(
            speaker=False,
            microphone=False,
            camera=False,
            led_neopixel=False,
            led_common_anode=True,
            servo=False,
        ),
        shine=SimpleNamespace(
            neopixel=None,
            common_anode=SimpleNamespace(red_pin=None, green_pin=None, blue_pin=None),
        ),
        see=None,
        listen=None,
        wave=None,
        speak=None,
    )

    with pytest.raises(TJBotError, match='Common-anode LED hardware is enabled'):
        bot._initialize_hardware_from_config()


@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
def test_tjbot_get_instance_singleton(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    TJBot._instance = None
    a = TJBot.get_instance()
    b = TJBot.get_instance()

    assert a is b
    a.initialize_sync()
    MockDriver.assert_called_once()


def test_tjbot_get_recipe_config(tmp_path, monkeypatch):
    recipe_path = tmp_path / "recipe.toml"
    recipe_path.write_text('[greeting]\nname = "tj"\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)

    recipe = TJBot.get_recipe_config()
    assert recipe["greeting"]["name"] == "tj"


@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
def test_tjbot_initialize_sync(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    assert bot.initialize_sync() is bot
    assert bot.rpi_model == "Raspberry Pi 4 Model B"


@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
def test_tjbot_shine_colors_and_random_color(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot()
    colors = bot.shine_colors()
    assert isinstance(colors, list)
    assert len(colors) > 0
    assert isinstance(bot.random_color(), str)


def test_tjbot_hardware_static_property():
    assert TJBot.Hardware.CAMERA == 'camera'
    assert TJBot.Hardware.MICROPHONE == 'microphone'


@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
def test_tjbot_get_local_models(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot()

    all_model_keys = bot.get_local_models(installed_only=False)
    stt_model_keys = bot.get_local_models(model_type='stt', installed_only=False)

    assert 'ssd-mobilenet-v2' in all_model_keys
    assert 'scrfd-2.5g' in all_model_keys
    assert any(model_key.startswith('whisper') for model_key in stt_model_keys)


def test_tjbot_cleanup_before_initialize_is_noop():
    bot = TJBot(auto_initialize=False)

    bot.cleanup()

    assert bot._initialized is False


def test_tjbot_concurrent_cleanup_waits_for_inflight_cleanup():
    bot = TJBot(auto_initialize=False)
    bot._initialized = True

    cleanup_started = threading.Event()
    release_cleanup = threading.Event()
    driver = mock.MagicMock()

    def blocking_cleanup():
        cleanup_started.set()
        release_cleanup.wait(timeout=2)

    driver.cleanup.side_effect = blocking_cleanup
    bot.rpi_driver = driver

    first_thread = threading.Thread(target=bot.cleanup)
    second_thread = threading.Thread(target=bot.cleanup)

    first_thread.start()
    assert cleanup_started.wait(timeout=1)

    second_thread.start()
    time.sleep(0.05)
    assert second_thread.is_alive() is True

    release_cleanup.set()
    first_thread.join(timeout=1)
    second_thread.join(timeout=1)

    assert first_thread.is_alive() is False
    assert second_thread.is_alive() is False
    driver.cleanup.assert_called_once()
    assert bot._initialized is False


@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
def test_tjbot_reinitialize_runs_cleanup_on_previous_driver(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    driver1 = mock.MagicMock()
    driver2 = mock.MagicMock()
    MockDriver.side_effect = [driver1, driver2]

    bot = TJBot(auto_initialize=False)
    bot.initialize_sync()
    bot.initialize_sync()

    driver1.cleanup.assert_called_once()
    assert bot.rpi_driver is driver2


@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
def test_tjbot_initialize_async_returns_self(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    result = asyncio.run(bot.initialize())

    assert result is bot
    assert bot._initialized is True


@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
@mock.patch('tjbot.tjbot.signal.signal')
@mock.patch('tjbot.tjbot.atexit.register')
def test_tjbot_initialize_async_installs_process_hooks(MockAtexitRegister, MockSignal, MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    result = asyncio.run(bot.initialize())

    assert result is bot
    MockAtexitRegister.assert_called_once()
    assert MockSignal.call_count == 3


@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
@mock.patch('tjbot.tjbot.signal.signal')
@mock.patch('tjbot.tjbot.atexit.register')
def test_tjbot_async_then_sync_initialize_does_not_reregister_hooks(
    MockAtexitRegister, MockSignal, MockDriver, MockDetect
):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    asyncio.run(bot.initialize())
    bot.initialize_sync()

    MockAtexitRegister.assert_called_once()
    assert MockSignal.call_count == 3


@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
@mock.patch('tjbot.tjbot.signal.signal')
@mock.patch('tjbot.tjbot.atexit.register')
def test_tjbot_process_hooks_installed_once(MockAtexitRegister, MockSignal, MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    bot.initialize_sync()
    bot.initialize_sync()

    MockAtexitRegister.assert_called_once()
    # Three signals should be registered once each.
    assert MockSignal.call_count == 3


@mock.patch('tjbot.tjbot.RPiDetect')
@mock.patch('tjbot.tjbot.RPi4Driver')
@mock.patch('tjbot.tjbot.signal.getsignal')
@mock.patch('tjbot.tjbot.signal.signal')
def test_tjbot_signal_handler_triggers_cleanup(MockSignalSet, MockSignalGet, MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True
    MockSignalGet.return_value = signal.SIG_DFL

    handlers = {}

    def capture_signal_handler(sig_value, handler):
        handlers[sig_value] = handler

    MockSignalSet.side_effect = capture_signal_handler

    bot = TJBot(auto_initialize=False)
    bot.initialize_sync()
    driver = bot.rpi_driver

    assert signal.SIGTERM in handlers
    handlers[signal.SIGTERM](signal.SIGTERM, None)

    assert driver is not None
    driver.cleanup.assert_called_once()
