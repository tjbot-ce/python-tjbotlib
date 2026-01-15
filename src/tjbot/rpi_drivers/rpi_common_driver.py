from typing import Optional
import logging

from .rpi_driver import RPiBaseHardwareDriver
from ..config.models import LEDCommonAnodeConfig, LEDNeopixelConfig, WaveConfig
from ..utils import Hardware, convert_hex_to_rgb_color
from ..led import LEDCommonAnode, LEDNeopixel
from ..servo import TJBotServo

logger = logging.getLogger(__name__)

class RPiCommonDriver(RPiBaseHardwareDriver):
    """
    Hardware driver for Raspberry Pi 3 and 4 (and Zero).
    Uses rpi_ws281x (PWM) for NeoPixel.
    Uses gpiozero/pigpio for GPIO/PWM.
    """
    def __init__(self):
        super().__init__()
        self.common_anode_led: Optional[LEDCommonAnode] = None
        self.neopixel_led: Optional[LEDNeopixel] = None
        self.servo: Optional[TJBotServo] = None

    def setup_led_common_anode(self, config: LEDCommonAnodeConfig) -> None:
        red_pin = config.redPin if config.redPin is not None else 19
        green_pin = config.greenPin if config.greenPin is not None else 13
        blue_pin = config.bluePin if config.bluePin is not None else 12

        self.common_anode_led = LEDCommonAnode(red_pin, green_pin, blue_pin)
        self.initialized_hardware.add(Hardware.LED_COMMON_ANODE)

    def setup_led_neopixel(self, config: LEDNeopixelConfig) -> None:
        pin = config.gpioPin if config.gpioPin is not None else 21

        self.neopixel_led = LEDNeopixel(pin)
        self.initialized_hardware.add(Hardware.LED_NEOPIXEL)

    def setup_servo(self, config: WaveConfig) -> None:
        pin = config.servoPin if config.servoPin is not None else 18
        self.servo = TJBotServo(pin)
        self.initialized_hardware.add(Hardware.SERVO)

    def render_led(self, hex_color: str) -> None:
        if self.has_hardware(Hardware.LED_COMMON_ANODE) and self.common_anode_led:
            rgb = convert_hex_to_rgb_color(hex_color)
            self.common_anode_led.render(rgb)

        if self.has_hardware(Hardware.LED_NEOPIXEL) and self.neopixel_led:
            # LEDNeopixel expects 0xRRGGBB int
            c = int(hex_color.lstrip('#'), 16)
            self.neopixel_led.render(c)

    def render_servo_position(self, position: int) -> None:
        if self.servo:
            pulse_ms = position / 1000.0
            self.servo.set_pulse_width(pulse_ms)
        else:
            logger.warning("Attempted to render on an uninitialized servo")
