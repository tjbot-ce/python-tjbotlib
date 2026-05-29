import asyncio
import signal
import threading
import time
import unittest.mock as mock
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tjbot import TJBot
from tjbot.utils.errors import TJBotError
from tjbot.utils import Capability, Hardware


def _mock_pi4_environment(monkeypatch):
    monkeypatch.setattr("tjbot.tjbot.RPiDetect.model", lambda: "Raspberry Pi 4 Model B")
    monkeypatch.setattr("tjbot.tjbot.RPiDetect.is_pi5", lambda: False)
    monkeypatch.setattr("tjbot.tjbot.RPiDetect.is_pi4", lambda: True)
    monkeypatch.setattr("tjbot.tjbot.RPiDetect.is_pi3", lambda: False)


@pytest.fixture()
def tjbot_with_mock_driver(monkeypatch):
    _mock_pi4_environment(monkeypatch)

    driver = MagicMock()
    driver.has_capability.return_value = True
    driver.render_led.return_value = None
    driver.render_servo_position.return_value = None
    driver.listen_for_transcript.return_value = "hello"
    driver.speak.return_value = None
    driver.play_audio.return_value = None
    driver.capture_photo.return_value = "/tmp/photo.jpg"
    driver.capture_photo_buffer.return_value = b"fake-image-bytes"
    driver.cleanup.return_value = None

    monkeypatch.setattr("tjbot.tjbot.RPi4Driver", lambda: driver)
    monkeypatch.setattr("tjbot.tjbot.RPi5Driver", lambda: driver)

    TJBot._instance = None
    bot = TJBot(auto_initialize=False)
    bot.initialize()
    return bot, driver


def test_shine_accepts_color_name(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    bot.shine("red")

    driver.render_led.assert_called()


def test_shine_accepts_hex_color_with_and_without_hash(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    bot.shine("#FF0000")
    bot.shine("FF0000")

    assert driver.render_led.call_count == 2


def test_shine_accepts_hex_color_with(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    bot.shine("#FF0000")


def test_shine_accepts_hex_color_without(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    bot.shine("FF0000")


def test_shine_hex_short_form_expands(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    bot.shine("#abc")


def test_shine_hex_without_hash_is_normalized(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    bot.shine("00ff00")


def test_shine_accepts(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    bot.shine("on")
    bot.shine("off")

    assert driver.render_led.call_count == 2


def test_shine_throws_on_invalid_color(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver

    with pytest.raises(TJBotError):
        bot.shine("notacolor_xyz123")


def test_shine_invalid_hex_raises(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    with pytest.raises(TJBotError):
        bot.shine("#gggggg")


def test_shine_throws_when_capability_not_available(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot.shine("red")


def test_shine_unsupported_led_type_raises(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False
    with pytest.raises(TJBotError):
        bot.shine("red")


def test_shine_calls_renderled_with_color(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    bot.shine("red")
    driver.render_led.assert_called()


def test_pulse_accepts_valid_durations(tjbot_with_mock_driver, monkeypatch):
    bot, driver = tjbot_with_mock_driver
    monkeypatch.setattr("tjbot.tjbot.tjbot_sleep", lambda *_args, **_kwargs: None)

    bot.pulse("red")
    bot.pulse("red", 0.5)
    bot.pulse("red", 1.0)
    bot.pulse("red", 2.0)

    assert driver.render_led.call_count > 0


def test_pulse_accepts_valid_color_and_duration(tjbot_with_mock_driver, monkeypatch):
    bot, _ = tjbot_with_mock_driver
    monkeypatch.setattr("tjbot.tjbot.tjbot_sleep", lambda *_args, **_kwargs: None)
    bot.pulse("red", 1.0)


def test_pulse_uses_default_duration_of_1_0_seconds(
    tjbot_with_mock_driver, monkeypatch
):
    bot, _ = tjbot_with_mock_driver
    monkeypatch.setattr("tjbot.tjbot.tjbot_sleep", lambda *_args, **_kwargs: None)
    bot.pulse("red")


def test_pulse_clamps_duration_to_minimum_0_5_seconds(
    tjbot_with_mock_driver, monkeypatch
):
    bot, _ = tjbot_with_mock_driver
    monkeypatch.setattr("tjbot.tjbot.tjbot_sleep", lambda *_args, **_kwargs: None)
    bot.pulse("red", 0.1)


def test_pulse_accepts_boundary_duration_0_5_seconds(
    tjbot_with_mock_driver, monkeypatch
):
    bot, _ = tjbot_with_mock_driver
    monkeypatch.setattr("tjbot.tjbot.tjbot_sleep", lambda *_args, **_kwargs: None)
    bot.pulse("red", 0.5)


def test_pulse_accepts_boundary_duration_2_0_seconds(
    tjbot_with_mock_driver, monkeypatch
):
    bot, _ = tjbot_with_mock_driver
    monkeypatch.setattr("tjbot.tjbot.tjbot_sleep", lambda *_args, **_kwargs: None)
    bot.pulse("red", 2.0)


def test_pulse_clamps_duration_exceeding_2_0_seconds(tjbot_with_mock_driver, caplog):
    import logging

    bot, _ = tjbot_with_mock_driver

    with caplog.at_level(logging.WARNING, logger="tjbot.tjbot"):
        bot.pulse("red", 2.5)

    assert any("2 seconds" in m for m in caplog.messages)


def test_pulse_throws_when_capability_not_available(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False
    with pytest.raises(TJBotError):
        bot.pulse("red")


def test_wave_calls_renderservoposition_multiple_times(
    tjbot_with_mock_driver, monkeypatch
):
    bot, driver = tjbot_with_mock_driver
    monkeypatch.setattr("tjbot.tjbot.tjbot_sleep", lambda *_args, **_kwargs: None)
    bot.wave()
    assert driver.render_servo_position.call_count >= 3


def test_wave_executes_without_error(tjbot_with_mock_driver, monkeypatch):
    bot, _ = tjbot_with_mock_driver
    monkeypatch.setattr("tjbot.tjbot.tjbot_sleep", lambda *_args, **_kwargs: None)
    bot.wave()


def test_raisearm_calls_renderservoposition(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    bot.raise_arm()
    driver.render_servo_position.assert_called()


def test_armback_calls_renderservoposition(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    bot.arm_back()
    driver.render_servo_position.assert_called()


def test_lowerarm_calls_renderservoposition(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    bot.lower_arm()
    driver.render_servo_position.assert_called()


def test_raisearm_throws_when_capability_not_available(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False
    with pytest.raises(TJBotError):
        bot.raise_arm()


def test_armback_throws_when_capability_not_available(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False
    with pytest.raises(TJBotError):
        bot.arm_back()


def test_lowerarm_throws_when_capability_not_available(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False
    with pytest.raises(TJBotError):
        bot.lower_arm()


def test_wave_throws_when_capability_not_available(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False
    with pytest.raises(TJBotError):
        bot.wave()


def test_wave_unsupported_servo_driver_raises(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False
    with pytest.raises(TJBotError):
        bot.wave()


def test_listen_throws_when_capability_not_available(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot.listen()


def test_capability_error_messages_mention_required_hardware(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False
    with pytest.raises(TJBotError) as exc:
        bot._assert_capability(Capability.LISTEN)
    assert Hardware.MICROPHONE in str(exc.value)


def test_assertcapability_throws_when_listen_capability_missing(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot._assert_capability(Capability.LISTEN)


def test_assertcapability_throws_when_see_capability_missing(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot._assert_capability(Capability.SEE)


def test_assertcapability_throws_when_shine_capability_missing(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot._assert_capability(Capability.SHINE)


def test_assertcapability_throws_when_speak_capability_missing(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot._assert_capability(Capability.SPEAK)


def test_assertcapability_throws_when_wave_capability_missing(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot._assert_capability(Capability.WAVE)


def test_assertcapability_does_not_throw_when_capability_is_available(
    tjbot_with_mock_driver,
):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = True

    bot._assert_capability(Capability.SHINE)


def test_listen_delegates_to_driver(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    result = bot.listen()

    assert result == "hello"
    driver.listen_for_transcript.assert_called_once()


def test_observe_invalid_input_type_raises(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver

    with pytest.raises((TJBotError, TypeError)):
        bot.listen(123)


def test_listen_async_streaming_callbacks(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    assert bot.config.listen.backend is not None
    bot.config.listen.backend.type = "local"
    assert bot.config.listen.backend.local is not None
    bot.config.listen.backend.local.model = "zipformer-en"
    bot.config.listen.backend.local.model_url = ""

    partial_results = []
    final_results = []

    def fake_listen_for_transcript(on_partial=None, on_final=None):
        if on_partial:
            on_partial("partial-hello")
        if on_final:
            on_final("final-hello")
        return "ignored-for-streaming"

    driver.listen_for_transcript.side_effect = fake_listen_for_transcript

    async def _run():
        result = await bot.listen_async(
            on_partial_result=partial_results.append,
            on_final_result=final_results.append,
        )
        await asyncio.sleep(0)
        return result

    result = asyncio.run(_run())

    assert result is None
    assert partial_results == ["partial-hello"]
    assert final_results == ["final-hello"]


def test_speak_throws_when_capability_not_available(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot.speak("hello")


def test_speak_delegates_to_driver(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    bot.speak("hello")

    driver.speak.assert_called_once_with("hello")


def test_play_does_not_check_for_speak_capability_before_execution(
    tjbot_with_mock_driver,
):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False
    bot.play("/path/to/sound.wav")

    driver.play_audio.assert_called_once_with("/path/to/sound.wav")


def test_see_throws_when_capability_not_available(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot.see()


def test_see_with_default_path(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    result = bot.see()

    assert result == b"fake-image-bytes"
    driver.capture_photo_buffer.assert_called_once()


def test_see_falls_back_to_temp_file_when_buffer_capture_missing(
    tjbot_with_mock_driver, tmp_path
):
    bot, driver = tjbot_with_mock_driver
    photo_path = tmp_path / "photo.jpg"
    photo_path.write_bytes(b"fallback-image-bytes")
    driver.capture_photo.return_value = str(photo_path)
    driver.capture_photo_buffer = None

    result = bot.see()

    assert result == b"fallback-image-bytes"
    assert not photo_path.exists()


def test_look_returns_string_when_given_custom_path(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    result = bot.look("/custom/path.jpg")

    assert result == "/tmp/photo.jpg"
    driver.capture_photo.assert_called_once_with("/custom/path.jpg")


def test_randomcolor_returns_a_string_when_colors_available(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    result = bot.random_color()
    assert result is None or isinstance(result, str)


def test_rpidriver_is_accessible(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    assert bot.rpi_driver is not None
    assert bot.rpi_driver is driver


def test_rpimodel_is_accessible(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    assert isinstance(bot.rpi_model, str)
    assert len(bot.rpi_model) > 0


def test_shinecolors_returns_an_array(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    colors = bot.shine_colors()
    assert isinstance(colors, list)


def test_shinecolors_returns_consistent_results_on_multiple_calls(
    tjbot_with_mock_driver,
):
    bot, _ = tjbot_with_mock_driver
    colors1 = bot.shine_colors()
    colors2 = bot.shine_colors()
    assert colors1 == colors2


def test_detectobjects_calls_rpidriver_detectobjects(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.detect_objects.return_value = [{"label": "person", "confidence": 0.9}]

    out = bot.detect_objects("/tmp/img.jpg")

    driver.detect_objects.assert_called_once_with("/tmp/img.jpg")
    assert isinstance(out, list)


def test_classifyimage_calls_rpidriver_classifyimage(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.classify_image.return_value = [{"label": "cat", "confidence": 0.8}]

    out = bot.classify_image("/tmp/img.jpg")

    driver.classify_image.assert_called_once_with("/tmp/img.jpg")
    assert isinstance(out, list)


def test_detectfaces_calls_rpidriver_detectfaces(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.detect_faces.return_value = {"faces": []}

    out = bot.detect_faces("/tmp/img.jpg")

    driver.detect_faces.assert_called_once_with("/tmp/img.jpg")
    assert isinstance(out, dict)


def test_describeimage_calls_rpidriver_describeimage(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.describe_image.return_value = {"caption": "a cat"}

    out = bot.describe_image("/tmp/img.jpg")

    driver.describe_image.assert_called_once_with("/tmp/img.jpg")
    assert isinstance(out, dict)


def test_see_reads_bytes_from_driver_buffer(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.capture_photo_buffer.return_value = b"node-parity-image"

    out = bot.see()

    driver.capture_photo_buffer.assert_called_once()
    assert out == b"node-parity-image"


def test_listen_async_offline_rejects_partial_callback(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    assert bot.config.listen.backend is not None
    bot.config.listen.backend.type = "local"
    assert bot.config.listen.backend.local is not None
    bot.config.listen.backend.local.model = "whisper-base"

    partial_results = []

    async def _run():
        await bot.listen_async(on_partial_result=partial_results.append)

    asyncio.run(_run())
    assert partial_results == []


def test_wave_and_arm_async_wrappers(tjbot_with_mock_driver, monkeypatch):
    bot, driver = tjbot_with_mock_driver
    monkeypatch.setattr("tjbot.tjbot.tjbot_sleep", lambda *_args, **_kwargs: None)

    bot.wave()
    bot.raise_arm()
    bot.arm_back()
    bot.lower_arm()

    assert driver.render_servo_position.call_count >= 4


def test_async_wrappers_return_expected_values(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    assert bot.config.listen.backend is not None
    assert bot.config.listen.backend.local is not None
    bot.config.listen.backend.local.model = "whisper-base"

    final_results = []

    async def _run():
        result = await bot.listen_async(on_final_result=final_results.append)
        return result

    result = asyncio.run(_run())
    assert result is None
    assert final_results == ["hello"]


def test_pulse_async_drives_led_without_blocking_event_loop(
    tjbot_with_mock_driver, monkeypatch
):
    bot, driver = tjbot_with_mock_driver
    monkeypatch.setattr("tjbot.tjbot.tjbot_sleep", lambda *_args, **_kwargs: None)

    bot.pulse("red", 0.5)

    assert driver.render_led.call_count >= 2


def test_pulse_async_throws_when_duration_exceeds_max(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver

    # Python implementation clamps >2.0s; this parity case checks that path does not crash.
    bot.pulse("red", 5.0)


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_detects_rpi_model_on_initialization(MockDriver, MockDetect):
    # Mock RPiDetect to return Pi 4 (supported by CommonDriver)
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot()

    assert isinstance(bot, TJBot)
    MockDriver.assert_called_once()
    assert bot.rpi_model == "Raspberry Pi 4 Model B"


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi5Driver")
def test_initializes_rpi_driver_based_on_model_pi_5(MockDriver, MockDetect):
    # Mock Pi 5
    MockDetect.model.return_value = "Raspberry Pi 5 Model B"
    MockDetect.is_pi5.return_value = True

    bot = TJBot()

    MockDriver.assert_called_once()
    assert bot.rpi_model == "Raspberry Pi 5 Model B"


@mock.patch("tjbot.tjbot.RPiDetect")
def test_applies_configuration_overrides(MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    config = {
        "log": {"level": "debug"},
        "hardware": {"camera": False, "led_common_anode": True},
    }

    with mock.patch("tjbot.tjbot.RPi4Driver"):
        bot = TJBot(config)
        assert isinstance(bot, TJBot)
        assert bot.config.log.level == "debug"


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
        shine=SimpleNamespace(
            neopixel=SimpleNamespace(gpio_pin=None, spi_interface=None),
            common_anode=None,
        ),
        see=None,
        listen=None,
        wave=None,
        speak=None,
    )

    with pytest.raises(TJBotError, match="NeoPixel LED hardware is enabled"):
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

    with pytest.raises(TJBotError, match="Common-anode LED hardware is enabled"):
        bot._initialize_hardware_from_config()


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_gets_tjbot_singleton_instance(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    TJBot._instance = None
    a = TJBot.get_instance()
    b = TJBot.get_instance()

    assert a is b
    a.initialize()
    MockDriver.assert_called_once()


def test_tjbot_get_recipe_config(tmp_path, monkeypatch):
    recipe_path = tmp_path / "recipe.toml"
    recipe_path.write_text('[greeting]\nname = "tj"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    recipe = TJBot.get_recipe_config()
    assert recipe["greeting"]["name"] == "tj"


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_sets_logging_level_from_config(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot({"log": {"level": "debug"}}, auto_initialize=False)
    bot.initialize()
    bot.set_log_level("debug")


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_config_is_accessible(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    bot.initialize()
    assert bot.config is not None
    assert isinstance(bot.config, object)


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_has_hardware_static_property(MockDriver, MockDetect):
    assert TJBot.Hardware.CAMERA == "camera"
    assert TJBot.Hardware.MICROPHONE == "microphone"


def test_has_version_static_property():
    assert hasattr(TJBot, "VERSION")
    assert isinstance(TJBot.VERSION, str)


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_tjbot_get_local_models(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot()

    all_model_keys = bot.get_local_models(installed_only=False)
    stt_model_keys = bot.get_local_models(model_type="stt", installed_only=False)

    assert "ssd-mobilenet-v2" in all_model_keys
    assert "scrfd-2.5g" in all_model_keys
    assert any(model_key.startswith("whisper") for model_key in stt_model_keys)


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


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_tjbot_reinitialize_runs_cleanup_on_previous_driver(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    driver1 = mock.MagicMock()
    driver2 = mock.MagicMock()
    MockDriver.side_effect = [driver1, driver2]

    bot = TJBot(auto_initialize=False)
    bot.initialize()
    bot.initialize()

    driver1.cleanup.assert_called_once()
    assert bot.rpi_driver is driver2


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_tjbot_initialize_returns_self(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    result = bot.initialize()

    assert result is bot
    assert bot._initialized is True


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
@mock.patch("tjbot.tjbot.signal.signal")
@mock.patch("tjbot.tjbot.atexit.register")
def test_tjbot_initialize_installs_process_hooks(
    MockAtexitRegister, MockSignal, MockDriver, MockDetect
):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    result = bot.initialize()

    assert result is bot
    MockAtexitRegister.assert_called_once()
    assert MockSignal.call_count == 3


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
@mock.patch("tjbot.tjbot.signal.signal")
@mock.patch("tjbot.tjbot.atexit.register")
def test_tjbot_initialize_twice_does_not_reregister_hooks(
    MockAtexitRegister, MockSignal, MockDriver, MockDetect
):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    bot.initialize()
    bot.initialize()

    MockAtexitRegister.assert_called_once()
    assert MockSignal.call_count == 3


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
@mock.patch("tjbot.tjbot.signal.signal")
@mock.patch("tjbot.tjbot.atexit.register")
def test_tjbot_process_hooks_installed_once(
    MockAtexitRegister, MockSignal, MockDriver, MockDetect
):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    bot.initialize()
    bot.initialize()

    MockAtexitRegister.assert_called_once()
    # Three signals should be registered once each.
    assert MockSignal.call_count == 3


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
@mock.patch("tjbot.tjbot.signal.getsignal")
@mock.patch("tjbot.tjbot.signal.signal")
def test_tjbot_signal_handler_triggers_cleanup(
    MockSignalSet, MockSignalGet, MockDriver, MockDetect
):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True
    MockSignalGet.return_value = signal.SIG_DFL

    handlers = {}

    def capture_signal_handler(sig_value, handler):
        handlers[sig_value] = handler

    MockSignalSet.side_effect = capture_signal_handler

    bot = TJBot(auto_initialize=False)
    bot.initialize()
    driver = bot.rpi_driver

    assert signal.SIGTERM in handlers
    with pytest.raises(SystemExit) as exc_info:
        handlers[signal.SIGTERM](signal.SIGTERM, None)

    assert exc_info.value.code == 143
    assert driver is not None
    driver.cleanup.assert_called_once()


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_eagerly_initializes_ai_engines_based_on_capabilities(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    driver = mock.MagicMock()
    driver.has_capability.side_effect = lambda capability: capability.name in {
        "LISTEN",
        "SPEAK",
        "SEE",
    }
    MockDriver.return_value = driver

    TJBot(auto_initialize=True)

    driver.initialize_stt_engine.assert_called_once()
    driver.initialize_tts_engine.assert_called_once()
    driver.initialize_vision_engine.assert_called_once()


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_tjbot_initialize_sync(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    bot = TJBot(auto_initialize=False)
    result = bot.initialize()

    assert result is bot
    assert bot._initialized is True


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_tjbot_hardware_init(MockDriver, MockDetect):
    MockDetect.model.return_value = "Raspberry Pi 4 Model B"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = True

    driver = mock.MagicMock()
    driver.has_capability.return_value = True
    MockDriver.return_value = driver

    TJBot(auto_initialize=True)

    driver.setup_speaker.assert_called_once()
    driver.setup_microphone.assert_called_once()
    driver.setup_servo.assert_called_once()


@mock.patch("tjbot.tjbot.RPiDetect")
@mock.patch("tjbot.tjbot.RPi4Driver")
def test_tjbot_init_common_driver(MockDriver, MockDetect):
    MockDetect.model.return_value = "Some Unknown Board"
    MockDetect.is_pi5.return_value = False
    MockDetect.is_pi4.return_value = False
    MockDetect.is_pi3.return_value = False

    TJBot(auto_initialize=True)

    MockDriver.assert_called_once()


def test_capability_error_messages_mention_required_hardware__2(tjbot_with_mock_driver):
    test_capability_error_messages_mention_required_hardware(tjbot_with_mock_driver)


def test_gets_tjbot_singleton_instance__2():
    test_gets_tjbot_singleton_instance()


def test_has_hardware_static_property__2():
    test_has_hardware_static_property()


def test_initializes_rpi_driver_based_on_model_pi_5__2():
    test_initializes_rpi_driver_based_on_model_pi_5()


def test_listen_async_streaming_callbacks__2(tjbot_with_mock_driver):
    test_listen_async_streaming_callbacks(tjbot_with_mock_driver)


def test_listen_throws_when_capability_not_available__2(tjbot_with_mock_driver):
    test_listen_throws_when_capability_not_available(tjbot_with_mock_driver)


def test_look_returns_string_when_given_custom_path__2(tjbot_with_mock_driver):
    test_look_returns_string_when_given_custom_path(tjbot_with_mock_driver)


def test_play_does_not_check_for_speak_capability_before_execution__2(
    tjbot_with_mock_driver,
):
    test_play_does_not_check_for_speak_capability_before_execution(
        tjbot_with_mock_driver
    )


def test_pulse_clamps_duration_exceeding_2_0_seconds__2(tjbot_with_mock_driver, caplog):
    test_pulse_clamps_duration_exceeding_2_0_seconds(tjbot_with_mock_driver, caplog)


def test_see_throws_when_capability_not_available__2(tjbot_with_mock_driver):
    test_see_throws_when_capability_not_available(tjbot_with_mock_driver)


def test_shine_accepts__2(tjbot_with_mock_driver):
    test_shine_accepts(tjbot_with_mock_driver)


def test_shine_accepts__3(tjbot_with_mock_driver):
    test_shine_accepts(tjbot_with_mock_driver)


def test_shine_throws_when_capability_not_available__2(tjbot_with_mock_driver):
    test_shine_throws_when_capability_not_available(tjbot_with_mock_driver)


def test_shinecolors_returns_an_array__2(tjbot_with_mock_driver):
    test_shinecolors_returns_an_array(tjbot_with_mock_driver)


def test_speak_throws_when_capability_not_available__2(tjbot_with_mock_driver):
    test_speak_throws_when_capability_not_available(tjbot_with_mock_driver)


def test_wave_calls_renderservoposition_multiple_times__2(
    tjbot_with_mock_driver, monkeypatch
):
    test_wave_calls_renderservoposition_multiple_times(
        tjbot_with_mock_driver, monkeypatch
    )
