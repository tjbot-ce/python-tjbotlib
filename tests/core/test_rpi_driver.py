from tjbot.rpi_drivers.rpi_driver import RPiBaseHardwareDriver
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

    assert driver.has_capability('listen') is True
    assert driver.has_capability('speak') is False


def test_has_hardware_led_unified_checks_led_variants():
    driver = DummyDriver()

    assert driver.has_hardware(Hardware.LED) is False

    driver.initialized_hardware.add(Hardware.LED_NEOPIXEL)
    assert driver.has_hardware(Hardware.LED) is True


def test_capture_photo_buffer_raises_when_camera_not_initialized():
    driver = DummyDriver()

    try:
        driver.capture_photo_buffer()
        assert False, 'Expected capture_photo_buffer to raise'
    except TJBotError as exc:
        assert 'Camera not initialized' in str(exc)
