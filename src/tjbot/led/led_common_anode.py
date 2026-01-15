from gpiozero import RGBLED
from typing import Tuple

class LEDCommonAnode:
    """
    LED controller for Common Anode LEDs using gpiozero.
    """
    def __init__(self, red_pin: int, green_pin: int, blue_pin: int):
        # gpiozero handles common anode (active_high=False)
        # However, Node implementation says "0 is ON, 255 is OFF" which implies active_low logic (sink).
        # gpiozero's RGBLED defaults to active_high=True (source).
        # If common anode, we connect anode to 3.3V, and pins to cathodes.
        # Pulling pin LOW turns LED ON.
        # So active_high should be False.
        self.led = RGBLED(red=red_pin, green=green_pin, blue=blue_pin, active_high=False)

    def render(self, rgb_color: Tuple[int, int, int]) -> None:
        """
        Render the LED to a specific RGB color.
        :param rgb_color: RGB color as (red, green, blue) where each is 0-255.
        """
        # gpiozero expects 0-1 floats
        r = rgb_color[0] / 255.0
        g = rgb_color[1] / 255.0
        b = rgb_color[2] / 255.0
        self.led.color = (r, g, b)

    def cleanup(self) -> None:
        self.led.close()
