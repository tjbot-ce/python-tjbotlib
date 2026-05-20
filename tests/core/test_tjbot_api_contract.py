import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from tjbot import TJBot
from tjbot.utils.errors import TJBotError
from tjbot.utils import Capability, Hardware


def _mock_pi4_environment(monkeypatch):
    monkeypatch.setattr('tjbot.tjbot.RPiDetect.model', lambda: 'Raspberry Pi 4 Model B')
    monkeypatch.setattr('tjbot.tjbot.RPiDetect.is_pi5', lambda: False)
    monkeypatch.setattr('tjbot.tjbot.RPiDetect.is_pi4', lambda: True)
    monkeypatch.setattr('tjbot.tjbot.RPiDetect.is_pi3', lambda: False)


@pytest.fixture()
def tjbot_with_mock_driver(monkeypatch):
    _mock_pi4_environment(monkeypatch)

    driver = MagicMock()
    driver.has_capability.return_value = True
    driver.render_led.return_value = None
    driver.render_servo_position.return_value = None
    driver.listen_for_transcript.return_value = 'hello'
    driver.speak.return_value = None
    driver.play_audio.return_value = None
    driver.capture_photo.return_value = '/tmp/photo.jpg'
    driver.capture_photo_buffer.return_value = b'fake-image-bytes'
    driver.cleanup.return_value = None

    monkeypatch.setattr('tjbot.tjbot.RPi4Driver', lambda: driver)
    monkeypatch.setattr('tjbot.tjbot.RPi5Driver', lambda: driver)

    TJBot._instance = None
    bot = TJBot(auto_initialize=False)
    bot.initialize_sync()
    return bot, driver


def test_shine_accepts_color_name(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    bot.shine('red')

    driver.render_led.assert_called()


def test_shine_accepts_hex_color_with_and_without_hash(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    bot.shine('#FF0000')
    bot.shine('FF0000')

    assert driver.render_led.call_count == 2


def test_shine_accepts_on_and_off(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    bot.shine('on')
    bot.shine('off')

    assert driver.render_led.call_count == 2


def test_shine_throws_on_invalid_color(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver

    with pytest.raises(TJBotError):
        bot.shine('notacolor_xyz123')


def test_shine_throws_when_capability_missing(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot.shine('red')


def test_pulse_accepts_valid_durations(tjbot_with_mock_driver, monkeypatch):
    bot, driver = tjbot_with_mock_driver
    monkeypatch.setattr('tjbot.tjbot.time.sleep', lambda *_args, **_kwargs: None)

    bot.pulse('red')
    bot.pulse('red', 0.5)
    bot.pulse('red', 1.0)
    bot.pulse('red', 2.0)

    assert driver.render_led.call_count > 0


def test_pulse_throws_when_duration_exceeds_max(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver

    with pytest.raises(TJBotError):
        bot.pulse('red', 2.5)


def test_pulse_async_drives_led_without_blocking_event_loop(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    async def _run():
        await bot.pulse_async('red', 0.5)

    asyncio.run(_run())

    assert driver.render_led.call_count > 0


def test_pulse_async_throws_when_duration_exceeds_max(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver

    with pytest.raises(TJBotError):
        asyncio.run(bot.pulse_async('red', 2.5))


def test_wave_calls_servo_multiple_times(tjbot_with_mock_driver, monkeypatch):
    bot, driver = tjbot_with_mock_driver
    monkeypatch.setattr('tjbot.tjbot.time.sleep', lambda *_args, **_kwargs: None)

    bot.wave()

    assert driver.render_servo_position.call_count >= 3


def test_wave_and_arm_async_wrappers(tjbot_with_mock_driver, monkeypatch):
    bot, driver = tjbot_with_mock_driver
    monkeypatch.setattr('tjbot.tjbot.time.sleep', lambda *_args, **_kwargs: None)

    asyncio.run(bot.arm_back_async())
    asyncio.run(bot.raise_arm_async())
    asyncio.run(bot.lower_arm_async())
    asyncio.run(bot.wave_async())

    assert driver.render_servo_position.call_count >= 6


def test_listen_requires_capability(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot.listen()


def test_capability_error_mentions_required_hardware(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError) as exc:
        bot._assert_capability(Capability.LISTEN)

    assert Hardware.MICROPHONE in str(exc.value)


def test_listen_delegates_to_driver(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    result = bot.listen()

    assert result == 'hello'
    driver.listen_for_transcript.assert_called_once()


def test_listen_async_streaming_callbacks(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    assert bot.config.listen.backend is not None
    bot.config.listen.backend.type = 'local'
    assert bot.config.listen.backend.local is not None
    bot.config.listen.backend.local.model = 'zipformer-en'
    bot.config.listen.backend.local.model_url = ''

    partial_results = []
    final_results = []

    def fake_listen_for_transcript(on_partial=None, on_final=None):
        if on_partial:
            on_partial('partial-hello')
        if on_final:
            on_final('final-hello')
        return 'ignored-for-streaming'

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
    assert partial_results == ['partial-hello']
    assert final_results == ['final-hello']


def test_listen_async_offline_rejects_partial_callback(tjbot_with_mock_driver):
    bot, _ = tjbot_with_mock_driver
    assert bot.config.listen.backend is not None
    assert bot.config.listen.backend.local is not None
    bot.config.listen.backend.local.model = 'whisper-base'

    with pytest.raises(TJBotError, match='offline'):
        asyncio.run(bot.listen_async(on_partial_result=lambda _text: None))


def test_speak_requires_capability(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot.speak('hello')


def test_speak_delegates_to_driver(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    bot.speak('hello')

    driver.speak.assert_called_once_with('hello')


def test_play_does_not_require_speak_capability(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    bot.play('/path/to/sound.wav')

    driver.play_audio.assert_called_once_with('/path/to/sound.wav')


def test_see_requires_capability(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver
    driver.has_capability.return_value = False

    with pytest.raises(TJBotError):
        bot.see()


def test_see_reads_bytes_from_driver_buffer(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    result = bot.see()

    assert result == b'fake-image-bytes'
    driver.capture_photo_buffer.assert_called_once()


def test_see_falls_back_to_temp_file_when_buffer_capture_missing(tjbot_with_mock_driver, tmp_path):
    bot, driver = tjbot_with_mock_driver
    photo_path = tmp_path / 'photo.jpg'
    photo_path.write_bytes(b'fallback-image-bytes')
    driver.capture_photo.return_value = str(photo_path)
    driver.capture_photo_buffer = None

    result = bot.see()

    assert result == b'fallback-image-bytes'
    assert not photo_path.exists()


def test_look_returns_driver_path(tjbot_with_mock_driver):
    bot, driver = tjbot_with_mock_driver

    result = bot.look('/custom/path.jpg')

    assert result == '/tmp/photo.jpg'
    driver.capture_photo.assert_called_once_with('/custom/path.jpg')


def test_async_wrappers_return_expected_values(tjbot_with_mock_driver, monkeypatch, tmp_path):
    bot, driver = tjbot_with_mock_driver
    monkeypatch.setattr('tjbot.tjbot.time.sleep', lambda *_args, **_kwargs: None)

    driver.capture_photo_buffer.return_value = b'async-image-bytes'

    assert asyncio.run(bot.listen_async()) == 'hello'
    assert asyncio.run(bot.speak_async('hello')) is None
    assert asyncio.run(bot.play_async('/path/to/sound.wav')) is None
    assert asyncio.run(bot.look_async('/custom/path.jpg')) == '/tmp/photo.jpg'
    assert asyncio.run(bot.see_async()) == b'async-image-bytes'
