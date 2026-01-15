from typing import Optional
import logging

from .rpi_driver import RPiBaseHardwareDriver
from ..config.models import LEDCommonAnodeConfig, LEDNeopixelConfig, WaveConfig
from ..utils import Hardware, convert_hex_to_rgb_color
from ..led import LEDCommonAnode, LEDNeopixelSPI
from ..servo import TJBotServo

logger = logging.getLogger(__name__)

class RPi5Driver(RPiBaseHardwareDriver):
    """
    Hardware driver for Raspberry Pi 5.
    Uses SPI for NeoPixel.
    Uses gpiozero/lgpio for GPIO/PWM.
    """
    def __init__(self):
        super().__init__()
        self.common_anode_led: Optional[LEDCommonAnode] = None
        self.neopixel_led: Optional[LEDNeopixelSPI] = None
        self.servo: Optional[TJBotServo] = None
        logger.debug("Pie initializing RPi5 hardware driver")

    def setup_led_common_anode(self, config: LEDCommonAnodeConfig) -> None:
        red_pin = config.redPin if config.redPin is not None else 19
        green_pin = config.greenPin if config.greenPin is not None else 13
        blue_pin = config.bluePin if config.bluePin is not None else 12

        logger.debug(f"Initializing {Hardware.LED_COMMON_ANODE} on R:{red_pin} G:{green_pin} B:{blue_pin}")
        self.common_anode_led = LEDCommonAnode(red_pin, green_pin, blue_pin)
        self.initialized_hardware.add(Hardware.LED_COMMON_ANODE)

    def setup_led_neopixel(self, config: LEDNeopixelConfig) -> None:
        spi_interface = config.spiInterface or '/dev/spidev0.0'
        use_grb = config.useGRBFormat or False

        logger.debug(f"Initializing {Hardware.LED_NEOPIXEL} on SPI {spi_interface}")
        self.neopixel_led = LEDNeopixelSPI(spi_interface, use_grb)
        self.initialized_hardware.add(Hardware.LED_NEOPIXEL)

    def setup_servo(self, config: WaveConfig) -> None:
        pin = config.servoPin if config.servoPin is not None else 18
        # gpioChip is handled by lgpio internals via gpiozero pin factory usually,
        # but gpiozero defaults to chip 0 or 4 depending on Pi model.
        # We assume gpiozero does the right thing with the pin number (BCM).

        self.servo = TJBotServo(pin)
        self.initialized_hardware.add(Hardware.SERVO)

    def render_led(self, hex_color: str) -> None:
        if self.has_hardware(Hardware.LED_COMMON_ANODE) and self.common_anode_led:
            rgb = convert_hex_to_rgb_color(hex_color)
            self.common_anode_led.render(rgb)

        if self.has_hardware(Hardware.LED_NEOPIXEL) and self.neopixel_led:
            self.neopixel_led.render(hex_color)

    def render_servo_position(self, position: int) -> None:
        if self.servo:
            # Position is in microseconds (500-2500)
            # TJBotServo expects milliseconds
            pulse_ms = position / 1000.0
            logger.debug(f"Setting servo position to {position} us ({pulse_ms} ms)")
            self.servo.set_pulse_width(pulse_ms)
        else:
            logger.warning("Attempted to render on an uninitialized servo")
