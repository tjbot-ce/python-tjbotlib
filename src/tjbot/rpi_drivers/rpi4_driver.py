from typing import Optional

from ..config.config_types import LEDCommonAnodeConfig, LEDNeopixelConfig, WaveConfig
from ..led import LEDCommonAnode, LEDNeopixel
from ..servo import LGPIOServoController
from ..utils import Hardware, convert_hex_to_rgb_color
from ..utils.logging import LogEmoji, get_logger
from .rpi_driver import RPiBaseHardwareDriver

logger = get_logger(__name__)
EMO = LogEmoji.RPI


class RPi4Driver(RPiBaseHardwareDriver):
    """Hardware driver for Raspberry Pi 4."""

    def __init__(self):
        super().__init__()
        self.common_anode_led: Optional[LEDCommonAnode] = None
        self.neopixel_led: Optional[LEDNeopixel] = None
        self.servo: Optional[LGPIOServoController] = None
        self.use_grb_format: bool = True
        logger.debug("%s initializing RPi4 hardware driver", EMO)

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
        pin = config.gpio_pin if config.gpio_pin is not None else 18
        logger.debug("%s initializing NeoPixel LED on pin %s", LogEmoji.LED, pin)
        self.neopixel_led = LEDNeopixel(pin)
        self.neopixel_led.initialize()
        self.use_grb_format = (
            config.use_grb_format if config.use_grb_format is not None else True
        )
        self.initialized_hardware.add(Hardware.LED)

    def setup_servo(self, config: WaveConfig) -> None:
        pin = config.servo_pin if config.servo_pin is not None else 18
        logger.debug(
            "%s initializing %s on PIN %s", LogEmoji.SERVO, Hardware.SERVO, pin
        )
        self.servo = LGPIOServoController(0, pin)
        self.initialized_hardware.add(Hardware.SERVO)

    def render_led_common_anode(self, rgb_color: tuple[int, int, int]) -> None:
        if self.common_anode_led:
            self.common_anode_led.render(rgb_color)
        else:
            logger.warning(
                "%s attempted to render on an uninitialized Common Anode LED",
                LogEmoji.LED,
            )

    def render_led_neopixel(self, hex_color: str) -> None:
        if not self.neopixel_led:
            logger.warning(
                "%s attempted to render on an uninitialized NeoPixel LED", LogEmoji.LED
            )
            return

        color = hex_color.lstrip("#")
        if len(color) != 6:
            logger.warning("%s invalid NeoPixel color '%s'", LogEmoji.LED, hex_color)
            return

        if self.use_grb_format:
            grb_str = f"{color[2:4]}{color[0:2]}{color[4:6]}"
            self.neopixel_led.render(int(grb_str, 16))
        else:
            self.neopixel_led.render(int(color, 16))

    def render_led(self, hex_color: str) -> None:
        if self.common_anode_led:
            rgb = convert_hex_to_rgb_color(hex_color)
            self.render_led_common_anode(rgb)

        if self.neopixel_led:
            self.render_led_neopixel(hex_color)

    def cleanup(self) -> None:
        if self.neopixel_led:
            self.neopixel_led.cleanup()
        super().cleanup()

    def render_servo_position(self, position: int) -> None:
        if self.servo:
            self.servo.set_position(position)
        else:
            logger.warning(
                "%s attempted to render on an uninitialized servo", LogEmoji.SERVO
            )
