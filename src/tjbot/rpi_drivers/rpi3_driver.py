# Copyright 2026-present TJBot Contributors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any

from ..config.config_types import LEDCommonAnodeConfig, LEDNeopixelConfig, WaveConfig
from ..led import LEDCommonAnode, LEDNeopixel
from ..servo import LGPIOServoController
from ..utils import Hardware, convert_hex_to_rgb_color
from ..utils.logging import get_logger
from .rpi_driver import RPiBaseHardwareDriver

logger = get_logger(__name__)


class RPi3Driver(RPiBaseHardwareDriver):
    """Hardware driver for Raspberry Pi 3 with local-AI performance warnings."""

    def __init__(self):
        super().__init__()
        self.common_anode_led = None
        self.neopixel_led = None
        self.servo = None
        self.use_grb_format = True
        self._user_has_been_warned: dict[str, bool] = {}
        logger.debug("initializing RPi3 hardware driver")

    def setup_led_common_anode(self, config: LEDCommonAnodeConfig) -> None:
        red_pin = config.red_pin if config.red_pin is not None else 19
        green_pin = config.green_pin if config.green_pin is not None else 13
        blue_pin = config.blue_pin if config.blue_pin is not None else 12
        logger.debug(
            "initializing Common Anode LED on RED PIN %s, GREEN PIN %s, and BLUE PIN %s",
            red_pin,
            green_pin,
            blue_pin,
        )
        self.common_anode_led = LEDCommonAnode(red_pin, green_pin, blue_pin)
        self.initialized_hardware.add(Hardware.LED)

    def setup_led_neopixel(self, config: LEDNeopixelConfig) -> None:
        pin = config.gpio_pin if config.gpio_pin is not None else 18
        logger.debug("initializing NeoPixel LED on pin %s", pin)
        self.neopixel_led = LEDNeopixel(pin)
        self.neopixel_led.initialize()
        self.use_grb_format = (
            config.use_grb_format if config.use_grb_format is not None else True
        )
        self.initialized_hardware.add(Hardware.LED)

    def setup_servo(self, config: WaveConfig) -> None:
        pin = config.servo_pin if config.servo_pin is not None else 18
        logger.debug("initializing %s on PIN %s", Hardware.SERVO, pin)
        self.servo = LGPIOServoController(0, pin)
        self.initialized_hardware.add(Hardware.SERVO)

    def render_led_common_anode(self, rgb_color: tuple[int, int, int]) -> None:
        if self.common_anode_led:
            self.common_anode_led.render(rgb_color)
        else:
            logger.warning("attempted to render on an uninitialized Common Anode LED")

    def render_led_neopixel(self, hex_color: str) -> None:
        if not self.neopixel_led:
            logger.warning("attempted to render on an uninitialized NeoPixel LED")
            return

        color = hex_color.lstrip("#")
        if len(color) != 6:
            logger.warning("invalid NeoPixel color '%s'", hex_color)
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
            logger.warning("attempted to render on an uninitialized servo")

    def _warn_if_using_local_ai(self, ai_type: str) -> None:
        if self._user_has_been_warned.get(ai_type):
            return

        if (
            ai_type == "stt"
            and self.listen_config
            and self.listen_config.backend
            and self.listen_config.backend.type == "local"
        ):
            logger.warning(
                "Using local STT on Raspberry Pi 3 may have poor performance. "
                "Consider using a cloud-based backend for better results."
            )
        elif (
            ai_type == "tts"
            and self.speak_config
            and self.speak_config.backend
            and self.speak_config.backend.type == "local"
        ):
            logger.warning(
                "Using local TTS on Raspberry Pi 3 may have poor performance. "
                "Consider using a cloud-based backend for better results."
            )
        elif (
            ai_type == "vision"
            and self.see_config
            and self.see_config.backend
            and self.see_config.backend.type == "local"
        ):
            logger.warning(
                "Using local Vision on Raspberry Pi 3 may have poor performance. "
                "Consider using a cloud-based backend for better results."
            )

        self._user_has_been_warned[ai_type] = True

    def listen_for_transcript(
        self, on_partial: Any = None, on_final: Any = None
    ) -> str:
        self._warn_if_using_local_ai("stt")
        return super().listen_for_transcript(on_partial=on_partial, on_final=on_final)

    def speak(self, message: str) -> None:
        self._warn_if_using_local_ai("tts")
        super().speak(message)

    def detect_objects(self, image: Any) -> Any:
        self._warn_if_using_local_ai("vision")
        return super().detect_objects(image)

    def classify_image(self, image: Any) -> Any:
        self._warn_if_using_local_ai("vision")
        return super().classify_image(image)

    def describe_image(self, image: Any) -> Any:
        self._warn_if_using_local_ai("vision")
        return super().describe_image(image)

    def detect_faces(self, image: Any) -> Any:
        self._warn_if_using_local_ai("vision")
        return super().detect_faces(image)
