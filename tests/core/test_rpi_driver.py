from unittest.mock import MagicMock
from tjbot.rpi_drivers.rpi_driver import RPiBaseHardwareDriver
from tjbot.rpi_drivers.rpi3_driver import RPi3Driver
from tjbot.rpi_drivers.rpi4_driver import RPi4Driver
from tjbot.utils.errors import TJBotError
from tjbot.utils import Hardware


class DummyDriver(RPiBaseHardwareDriver):
    def setup_led_common_anode(self, config):
        _ = config

    def setup_led_neopixel(self, config):
        _ = config

    def setup_servo(self, config):
        _ = config

    def render_led(self, hex_color: str) -> None:
        _ = hex_color

    def render_led_common_anode(self, rgb_color: tuple) -> None:
        _ = rgb_color

    def render_led_neopixel(self, hex_color: str) -> None:
        _ = hex_color

    def render_servo_position(self, position: int) -> None:
        _ = position


def test_get_hardware_returns_copy_of_initialized_hardware():
    driver = DummyDriver()
    driver.initialized_hardware.update({Hardware.CAMERA, Hardware.SPEAKER})

    hardware = driver.get_hardware()

    assert hardware == {Hardware.CAMERA, Hardware.SPEAKER}
    hardware.add(Hardware.SERVO)
    assert Hardware.SERVO not in driver.initialized_hardware


def test_has_capability_uses_initialized_hardware_set():
    driver = DummyDriver()
    driver.initialized_hardware.add(Hardware.MICROPHONE)

    assert driver.has_capability("listen") is True
    assert driver.has_capability("speak") is False


def test_has_hardware_led_unified_checks_led_variants():
    driver = DummyDriver()

    assert driver.has_hardware(Hardware.LED) is False

    driver.initialized_hardware.add(Hardware.LED)
    assert driver.has_hardware(Hardware.LED) is True


def test_capture_photo_buffer_raises_when_camera_not_initialized():
    driver = DummyDriver()

    try:
        driver.capture_photo_buffer()
        assert False, "Expected capture_photo_buffer to raise"
    except TJBotError as exc:
        assert "Camera not initialized" in str(exc)


# ---------------------------------------------------------------------------
# RPi3Driver NeoPixel color conversion
# ---------------------------------------------------------------------------


def _make_rpi3_with_mock_neopixel(use_grb: bool = True) -> tuple:
    driver = RPi3Driver()
    mock_led = MagicMock()
    driver.neopixel_led = mock_led
    driver.use_grb_format = use_grb
    return driver, mock_led


def test_rpi3driver_converts_rgb_to_grb_when_configured():
    driver, mock_led = _make_rpi3_with_mock_neopixel(use_grb=True)
    # Red: #FF0000 → GRB swap: G=00, R=FF, B=00 → 0x00FF00
    driver.render_led_neopixel("#FF0000")
    mock_led.render.assert_called_once_with(0x00FF00)


def test_rpi3driver_parses_bare_rgb_hex_correctly():
    driver, mock_led = _make_rpi3_with_mock_neopixel(use_grb=False)
    # Bare hex without '#': FF0000 → 0xFF0000
    driver.render_led_neopixel("FF0000")
    mock_led.render.assert_called_once_with(0xFF0000)


# ---------------------------------------------------------------------------
# RPi4Driver NeoPixel color conversion
# ---------------------------------------------------------------------------


def _make_rpi4_with_mock_neopixel(use_grb: bool = False) -> tuple:
    driver = RPi4Driver()
    mock_led = MagicMock()
    driver.neopixel_led = mock_led
    driver.use_grb_format = use_grb
    return driver, mock_led


def test_rpi4driver_parses_bare_rgb_hex_correctly():
    driver, mock_led = _make_rpi4_with_mock_neopixel(use_grb=False)
    # Bare hex without '#': 0000FF → 0x0000FF
    driver.render_led_neopixel("0000FF")
    mock_led.render.assert_called_once_with(0x0000FF)
