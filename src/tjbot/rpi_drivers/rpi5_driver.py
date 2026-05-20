from typing import Optional

from .rpi_driver import RPiBaseHardwareDriver
from ..config.config_types import LEDCommonAnodeConfig, LEDNeopixelConfig, WaveConfig
from ..utils import Hardware, convert_hex_to_rgb_color
from ..led import LEDCommonAnode, LEDNeopixelSPI
from ..servo import LGPIOServoController
from ..utils.logging import LogEmoji, get_logger

logger = get_logger(__name__)
EMO = LogEmoji.RPI

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
        self.servo: Optional[LGPIOServoController] = None
        logger.debug("%s initializing RPi5 hardware driver", EMO)

    def setup_led_common_anode(self, config: LEDCommonAnodeConfig) -> None:
        red_pin = config.red_pin if config.red_pin is not None else 19
        green_pin = config.green_pin if config.green_pin is not None else 13
        blue_pin = config.blue_pin if config.blue_pin is not None else 12

        logger.debug(
            "%s initializing Common Anode LED on RED PIN %s, GREEN PIN %s, and BLUE PIN %s",
            LogEmoji.LED,
            red_pin,
            green_pin,
            blue_pin,
        )
        self.common_anode_led = LEDCommonAnode(red_pin, green_pin, blue_pin)
        self.initialized_hardware.add(Hardware.LED)

    def setup_led_neopixel(self, config: LEDNeopixelConfig) -> None:
        spi_interface = config.spi_interface if config.spi_interface is not None else "/dev/spidev0.0"
        use_grb = config.use_grb_format if config.use_grb_format is not None else False

        logger.debug("%s initializing NeoPixel LED on SPI %s", LogEmoji.LED, spi_interface)
        self.neopixel_led = LEDNeopixelSPI(spi_interface, use_grb)
        self.initialized_hardware.add(Hardware.LED)

    def setup_servo(self, config: WaveConfig) -> None:
        pin = config.servo_pin if config.servo_pin is not None else 18
        logger.debug("%s initializing %s on PIN %s", LogEmoji.SERVO, Hardware.SERVO, pin)
        self.servo = LGPIOServoController(0, pin)
        self.initialized_hardware.add(Hardware.SERVO)

    def render_led_common_anode(self, rgb_color: tuple[int, int, int]) -> None:
        if self.common_anode_led:
            self.common_anode_led.render(rgb_color)
        else:
            logger.warning("%s attempted to render on an uninitialized Common Anode LED", LogEmoji.LED)

    def render_led_neopixel(self, hex_color: str) -> None:
        if self.neopixel_led:
            self.neopixel_led.render(hex_color)
        else:
            logger.warning("%s attempted to render on an uninitialized NeoPixel LED", LogEmoji.LED)

    def render_led(self, hex_color: str) -> None:
        if self.common_anode_led:
            rgb = convert_hex_to_rgb_color(hex_color)
            self.render_led_common_anode(rgb)

        if self.neopixel_led:
            self.render_led_neopixel(hex_color)

    def render_servo_position(self, position: int) -> None:
        if self.servo:
            self.servo.set_position(position)
        else:
            logger.warning("%s attempted to render on an uninitialized servo", LogEmoji.SERVO)
