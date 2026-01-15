import logging
import time
from typing import Optional, Dict, Any, List, Union, Callable

from .config import TJBotConfig
from .error import TJBotError
from .utils import Hardware, Capability, normalize_color
from .servo import ServoPosition
from .rpi_drivers import RPiHardwareDriver, RPi5Driver, RPiCommonDriver, RPiDetect

# Setup logging
logging.basicConfig()
logger = logging.getLogger("tjbot")

class TJBot:
    """
    Class representing a TJBot.
    """
    VERSION = "0.1.0"

    def __init__(self, override_config: Optional[Dict[str, Any]] = None):
        self.config = TJBotConfig(override_config)

        # Configure logging
        if self.config.log.level:
            logger.setLevel(self.config.log.level.upper())

        self._shine_colors: List[str] = []

        # Detect RPi
        self.rpi_model = RPiDetect.model()
        logger.info(f"👋 Hello from TJBot! Running on {self.rpi_model}")

        # Select Driver
        self.rpi_driver: RPiHardwareDriver
        if RPiDetect.is_pi5():
            self.rpi_driver = RPi5Driver()
        elif RPiDetect.is_pi4() or RPiDetect.is_pi3():
            self.rpi_driver = RPiCommonDriver()
        else:
             logger.warning(f"TJBot is running on unsupported hardware: {self.rpi_model}. Defaulting to Common Driver.")
             self.rpi_driver = RPiCommonDriver()

        # Initialize Hardware
        self._initialize_hardware_from_config()

    def _initialize_hardware_from_config(self):
        hw_config = self.config.hardware
        enabled_hardware: List[str] = []

        # Determine what to init
        if hw_config.speaker:
            enabled_hardware.append(Hardware.SPEAKER)
        if hw_config.microphone:
            enabled_hardware.append(Hardware.MICROPHONE)
        if hw_config.camera:
            enabled_hardware.append(Hardware.CAMERA)
        if hw_config.led_neopixel:
            enabled_hardware.append(Hardware.LED_NEOPIXEL)
        if hw_config.led_common_anode:
            enabled_hardware.append(Hardware.LED_COMMON_ANODE)
        if hw_config.servo:
            enabled_hardware.append(Hardware.SERVO)

        if not enabled_hardware:
            logger.debug("No hardware configured in config file")
            return

        logger.info(f"🤖 Initializing TJBot with {', '.join(enabled_hardware)}")

        for hw in enabled_hardware:
            if hw == Hardware.CAMERA:
                self.rpi_driver.setup_camera(self.config.see)
            elif hw == Hardware.LED_NEOPIXEL:
                # Type guard for mypy
                # cfg = self.config.shine.neopixel if self.config.shine.neopixel else None
                # We need to construct a valid config object if None, or handle in setup
                # Config model defaults to None, let's pass dummy or handle in driver
                # Driver expects config object.
                # Actually ConfigModel defaults ensure fields exist but might be None.
                # Let's rely on config being populated by TJBotConfig defaults
                if self.config.shine.neopixel:
                     self.rpi_driver.setup_led_neopixel(self.config.shine.neopixel)
            elif hw == Hardware.LED_COMMON_ANODE:
                if self.config.shine.commonanode:
                    self.rpi_driver.setup_led_common_anode(self.config.shine.commonanode)
            elif hw == Hardware.MICROPHONE:
                self.rpi_driver.setup_microphone(self.config.listen)
            elif hw == Hardware.SERVO:
                self.rpi_driver.setup_servo(self.config.wave)
            elif hw == Hardware.SPEAKER:
                self.rpi_driver.setup_speaker(self.config.speak)

    def _assert_capability(self, capability: str):
        if not self.rpi_driver.has_capability(capability):
            raise TJBotError(f"TJBot is not configured to {capability}.")

    # --- SHINE ---
    def shine(self, color: str) -> None:
        """
        Change the color of the LED.
        :param color: Hex color, name, "on", or "off".
        """
        self._assert_capability(Capability.SHINE)
        c = normalize_color(color)
        # remove leading # for driver if needed?
        # Drivers accept #RRGGBB or RRGGBB usually.
        # rpi5_driver converts hex string using convert_hex_to_rgb or passes to spi.
        # utils.normalize_color returns #RRGGBB.
        # rpi_common_driver led_neopixel expects int(hex).
        # Let's strip # just in case driver expects clean hex.
        # Actually standardizing on #RRGGBB is better, but existing driver code might assume no #.
        # rpi5_driver `render_led` -> `convert_hex_to_rgb_color` strips #. `neopixel_led.render` (SPI) parses int(color, 16) which handles 0x but maybe not #.
        # `int("#ffffff", 16)` fails. `int("ffffff", 16)` works.
        # So I should strip # before calling driver render_led.
        if c.startswith('#'):
            c = c[1:]

        # Async in Node? Node `shine` is async. Python usually sync unless using asyncio.
        # RPi driver `render_led` is sync.
        self.rpi_driver.render_led(c)

    def pulse(self, color: str, duration: float = 1.0) -> None:
        """
        Pulse the LED a single time.
        """
        self._assert_capability(Capability.SHINE)

        if duration < 0.5:
            logger.warning("TJBot cannot pulse for less than 0.5 seconds")
            duration = 0.5
        if duration > 2.0:
             logger.warning("TJBot cannot pulse for more than 2.0 seconds")
             duration = 2.0

        num_steps = 20
        # fps = num_steps / duration
        # delay = 1.0 / fps # delay between steps

        # Ease function: quadratic in-out
        # t: current time, b: start, c: change, d: duration
        def ease_in_out_quad(t, b, c, d):
            t /= d / 2
            if t < 1:
                return c / 2 * t * t + b
            t -= 1
            return -c / 2 * (t * (t - 2) - 1) + b

        # Generate brightness/color ramp
        # Node impl generates a color ramp by varying lightness in HSL.
        # We can implement similar or just fade from OFF to COLOR to OFF?
        # Node: "colorRamp[i] = hex.toHsl().lightness(l).toRgb()..."
        # It ramps lightness from 0.0 to 0.5.

        import webcolors
        import colorsys

        rgb_target = webcolors.hex_to_rgb(normalize_color(color)) # (r, g, b)
        # Convert to HLS (Hue, Lightness, Saturation)
        h, lightness, s = colorsys.rgb_to_hls(rgb_target.red/255.0, rgb_target.green/255.0, rgb_target.blue/255.0)

        # We want to ramp L from 0 to 0.5 (or target L?)
        # Node code: `l = 0.0 + (i / (numSteps / 2)) * 0.5;`
        # This implies it peaks at L=0.5. If the color is lighter than 0.5, it might look weird?
        # Assuming standard LED behavior, max brightness is usually decent.

        ramp_colors = []
        half_steps = int(num_steps / 2)
        for i in range(half_steps):
             l_val = (i / half_steps) * 0.5
             r, g, b = colorsys.hls_to_rgb(h, l_val, s)
             ramp_colors.append(webcolors.rgb_to_hex((int(r*255), int(g*255), int(b*255))))

        # Full ramp: up + down
        full_ramp = ramp_colors + ramp_colors[::-1]

        # Easing logic to create delays
        # Node creates 'ease' array of times, then diffs them to get delays.
        ease_times = []
        for i in range(len(full_ramp)):
             t = ease_in_out_quad(i, 0, 1, len(full_ramp))
             ease_times.append(t * duration)

        # Delays
        # Wait, if we use time.sleep, we need delta.
        # Node: ease = ease.map(x => x * duration); easeDelays[i] = ease[i+1] - ease[i];

        prev_time = 0
        for i, c in enumerate(full_ramp):
             # Calculate sleep time
             target_time = ease_times[i]
             sleep_time = target_time - prev_time
             if sleep_time > 0:
                 time.sleep(sleep_time)

             # Render
             if c.startswith('#'):
                 c = c[1:]
             self.rpi_driver.render_led(c)
             prev_time = target_time

    # --- WAVE ---
    def arm_back(self):
        self._assert_capability(Capability.WAVE)
        self.rpi_driver.render_servo_position(ServoPosition.ARM_BACK)

    def raise_arm(self):
        self._assert_capability(Capability.WAVE)
        self.rpi_driver.render_servo_position(ServoPosition.ARM_UP)

    def lower_arm(self):
        self._assert_capability(Capability.WAVE)
        self.rpi_driver.render_servo_position(ServoPosition.ARM_DOWN)

    def wave(self):
        self._assert_capability(Capability.WAVE)
        delay = 0.2
        self.rpi_driver.render_servo_position(ServoPosition.ARM_UP)
        time.sleep(delay)
        self.rpi_driver.render_servo_position(ServoPosition.ARM_DOWN)
        time.sleep(delay)
        self.rpi_driver.render_servo_position(ServoPosition.ARM_UP)

    # --- SPEAK ---
    def speak(self, message: str):
        self._assert_capability(Capability.SPEAK)
        logger.info(f"💬 TJBot speaking: '{message}'")
        self.rpi_driver.speak(message)

    def play(self, sound_file: str):
        self.rpi_driver.play_audio(sound_file)

    # --- LISTEN ---
    def listen(self, callback: Optional[Callable[[str], None]] = None) -> Union[str, None]:
        """
        Listen for speech.
        :param callback: If provided, streaming mode is assumed (partial/final results via callback).
                         If None, blocking single-shot mode is assumed.
        """
        self._assert_capability(Capability.LISTEN)

        if callback:
             # Streaming / Callback mode
             # Node: return await this.rpiDriver.listenForTranscript({ onPartial: ..., onFinal: ... })
             # Python: blocking listen but calls callbacks?
             # Ideally this should be async or threaded if we want 'streaming' while doing other things,
             # but here we follow sync blocking pattern for 'listen'.
             self.rpi_driver.listen_for_transcript(on_final=callback, on_partial=callback)
             return None
        else:
             # Single shot
             return self.rpi_driver.listen_for_transcript()

    # --- LOOK ---
    def look(self, file_path: Optional[str] = None) -> str:
        self._assert_capability(Capability.LOOK)
        return self.rpi_driver.capture_photo(file_path)
