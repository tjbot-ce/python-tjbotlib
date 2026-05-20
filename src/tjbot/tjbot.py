import asyncio
import atexit
import os
import random
import signal
import threading
import time
from typing import Optional, Dict, Any, List, Union, Callable

import webcolors

from .config import TJBotConfig
from .utils.errors import TJBotError
from .utils import Hardware, Capability, ModelRegistry, get_logger, get_shine_colors, init_logging, normalize_color, set_log_level
from .servo import ServoPosition
from .rpi_drivers import RPiHardwareDriver, RPi3Driver, RPi4Driver, RPi5Driver, RPiDetect
from .stt.stt_utils import infer_stt_mode

init_logging("info")
logger = get_logger(__name__)


_CAPABILITY_HARDWARE_MAP = {
    Capability.LISTEN: Hardware.MICROPHONE,
    Capability.SEE: Hardware.CAMERA,
    Capability.SHINE: Hardware.LED,
    Capability.SPEAK: Hardware.SPEAKER,
    Capability.WAVE: Hardware.SERVO,
}

class TJBot:
    """
    Class representing a TJBot.
    """
    VERSION = "0.1.0"
    Hardware = Hardware
    _instance: Optional["TJBot"] = None

    def __init__(
        self,
        override_config: Optional[Dict[str, Any]] = None,
        recipe_config_path: str = "recipe.toml",
        auto_initialize: bool = True,
    ):
        self.config = TJBotConfig(override_config, recipe_config_path)

        # Configure logging
        if self.config.log.level:
            set_log_level(self.config.log.level)

        self._shine_colors: List[str] = []
        self._initialized = False
        self._cleanup_in_progress = False
        self._cleanup_condition = threading.Condition()
        self._cleanup_run_id = 0
        self._cleanup_completed_run_id = 0
        self._cleanup_error: Optional[Exception] = None
        self._process_hooks_installed = False

        self.rpi_model: str = ""
        self.rpi_driver: Optional[RPiHardwareDriver] = None

        if auto_initialize:
            self._initialize_sync(override_config, recipe_config_path)

    @classmethod
    def get_instance(cls) -> "TJBot":
        if cls._instance is None:
            cls._instance = cls(auto_initialize=False)
        return cls._instance

    @classmethod
    def get_recipe_config(cls, recipe_config_path: str = "recipe.toml") -> Dict[str, Any]:
        config = TJBotConfig(recipe_config_path=recipe_config_path)
        return config.recipe

    async def initialize(
        self,
        override_config: Optional[Dict[str, Any]] = None,
        recipe_config_path: str = "recipe.toml",
    ) -> "TJBot":
        # Ensure lifecycle hooks are registered even when callers only use async initialize.
        self._install_process_cleanup_hooks()
        await asyncio.to_thread(self._initialize_sync, override_config, recipe_config_path)
        return self

    def initialize_sync(
        self,
        override_config: Optional[Dict[str, Any]] = None,
        recipe_config_path: str = "recipe.toml",
    ) -> "TJBot":
        self._initialize_sync(override_config, recipe_config_path)
        return self

    def _initialize_sync(
        self,
        override_config: Optional[Dict[str, Any]] = None,
        recipe_config_path: str = "recipe.toml",
    ) -> None:
        self._install_process_cleanup_hooks()

        if self._initialized:
            self.cleanup()

        self.config = TJBotConfig(override_config, recipe_config_path)

        # Configure logging
        if self.config.log.level:
            set_log_level(self.config.log.level)

        # Detect RPi
        self.rpi_model = RPiDetect.model()
        logger.info(f"Hello from TJBot! Running on {self.rpi_model}")

        # Select Driver
        if RPiDetect.is_pi5():
            self.rpi_driver = RPi5Driver()
        elif RPiDetect.is_pi4():
            self.rpi_driver = RPi4Driver()
        elif RPiDetect.is_pi3():
            self.rpi_driver = RPi3Driver()
        else:
            logger.warning(
                f"TJBot is running on unsupported hardware: {self.rpi_model}. Defaulting to Common Driver."
            )
            self.rpi_driver = RPi4Driver()

        # Initialize Hardware
        self._initialize_hardware_from_config()

        # Eagerly initialize AI models for configured capabilities.
        self._initialize_ai_models()
        self._initialized = True

    def _initialize_ai_models(self) -> None:
        if self.rpi_driver is None:
            return

        if self.rpi_driver.has_capability(Capability.LISTEN):
            self.rpi_driver.initialize_stt_engine()

        if self.rpi_driver.has_capability(Capability.SPEAK):
            self.rpi_driver.initialize_tts_engine()

        if self.rpi_driver.has_capability(Capability.SEE):
            self.rpi_driver.initialize_vision_engine()

    def cleanup(self) -> None:
        with self._cleanup_condition:
            if self._cleanup_in_progress:
                wait_run_id = self._cleanup_run_id
                while self._cleanup_in_progress and self._cleanup_run_id == wait_run_id:
                    self._cleanup_condition.wait()

                if self._cleanup_completed_run_id == wait_run_id and self._cleanup_error is not None:
                    raise TJBotError("Failed to clean up TJBot resources", cause=self._cleanup_error)
                return

            self._cleanup_in_progress = True
            self._cleanup_run_id += 1
            run_id = self._cleanup_run_id
            self._cleanup_error = None

        driver = self.rpi_driver
        cleanup_error: Optional[Exception] = None
        try:
            if driver is None:
                self._initialized = False
                return

            cleanup = getattr(driver, "cleanup", None)
            if callable(cleanup):
                cleanup()
            self._initialized = False
        except Exception as error:
            cleanup_error = error if isinstance(error, Exception) else Exception(str(error))
            raise TJBotError("Failed to clean up TJBot resources", cause=cleanup_error)
        finally:
            with self._cleanup_condition:
                self._cleanup_in_progress = False
                self._cleanup_completed_run_id = run_id
                self._cleanup_error = cleanup_error
                self._cleanup_condition.notify_all()

    def _install_process_cleanup_hooks(self) -> None:
        if self._process_hooks_installed:
            return

        # Python only permits signal registration in the main thread.
        if threading.current_thread() is not threading.main_thread():
            return

        atexit.register(self._run_lifecycle_cleanup)

        for sig_name in ("SIGINT", "SIGTERM", "SIGHUP"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue

            previous = signal.getsignal(sig)

            def _handler(signum, frame, prev=previous):
                _ = frame
                self._run_lifecycle_cleanup()
                if callable(prev):
                    prev(signum, frame)

            signal.signal(sig, _handler)

        self._process_hooks_installed = True

    def _run_lifecycle_cleanup(self) -> None:
        try:
            self.cleanup()
        except Exception as error:
            logger.warning("TJBot lifecycle cleanup failed: %s", error)

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
        if getattr(hw_config, "led", False) or getattr(hw_config, "led_neopixel", False) or getattr(hw_config, "led_common_anode", False):
            enabled_hardware.append(Hardware.LED)
        if hw_config.servo:
            enabled_hardware.append(Hardware.SERVO)

        if not enabled_hardware:
            logger.debug("No hardware configured in config file")
            return

        logger.info(f"Initializing TJBot with {', '.join(enabled_hardware)}")

        for hw in enabled_hardware:
            if hw == Hardware.CAMERA:
                self.rpi_driver.setup_camera(self.config.see)
            elif hw == Hardware.LED:
                shine_config = self.config.shine
                has_neopixel = bool((shine_config.has_neopixel_led if shine_config else False) or getattr(hw_config, "led_neopixel", False))
                has_common_anode = bool((shine_config.has_common_anode_led if shine_config else False) or getattr(hw_config, "led_common_anode", False))

                if not has_neopixel and not has_common_anode:
                    raise TJBotError(
                        "LED hardware enabled but no LED type configured. Set shine.hasNeopixelLED or "
                        "shine.hasCommonAnodeLED to true in your tjbot configuration file (~/.tjbot/tjbot.toml)."
                    )

                if has_neopixel:
                    neopixel = shine_config.neopixel
                    if not neopixel or (neopixel.gpio_pin is None and not neopixel.spi_interface):
                        raise TJBotError(
                            "NeoPixel LED hardware is enabled but shine.neopixel is not configured. "
                            "Define [shine.neopixel] in your tjbot configuration."
                        )
                    self.rpi_driver.setup_led_neopixel(neopixel)

                if has_common_anode:
                    common_anode = shine_config.common_anode
                    if not common_anode or (
                        common_anode.red_pin is None
                        or common_anode.green_pin is None
                        or common_anode.blue_pin is None
                    ):
                        raise TJBotError(
                            "Common-anode LED hardware is enabled but shine.commonanode is not configured. "
                            "Define [shine.commonanode] in your tjbot configuration."
                        )
                    self.rpi_driver.setup_led_common_anode(common_anode)
            elif hw == Hardware.MICROPHONE:
                self.rpi_driver.setup_microphone(self.config.listen)
            elif hw == Hardware.SERVO:
                self.rpi_driver.setup_servo(self.config.wave)
            elif hw == Hardware.SPEAKER:
                self.rpi_driver.setup_speaker(self.config.speak)

    def _assert_capability(self, capability: str):
        if not self._initialized:
            raise TJBotError("TJBot has not been initialized. Call initialize() before using TJBot methods.")
        if not self.rpi_driver.has_capability(capability):
            required_hardware = _CAPABILITY_HARDWARE_MAP.get(capability)
            if required_hardware:
                raise TJBotError(
                    f"TJBot is not configured to {capability}. Required hardware: {required_hardware}."
                )
            raise TJBotError(f"TJBot is not configured to {capability}.")

    def set_log_level(self, level: str) -> None:
        set_log_level(level)

    async def sleep(self, sec: float) -> None:
        await asyncio.sleep(sec)

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
            # rpi3/rpi4 LEDNeopixel expects an int color value.
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

    async def shine_async(self, color: str) -> None:
        await asyncio.to_thread(self.shine, color)

    def pulse(self, color: str, duration: float = 1.0) -> None:
        """
        Pulse the LED a single time.
        """
        self._assert_capability(Capability.SHINE)

        if duration < 0.5:
            logger.warning("TJBot cannot pulse for less than 0.5 seconds")
            duration = 0.5
        if duration > 2.0:
            raise TJBotError("TJBot cannot pulse for more than 2.0 seconds")

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

    async def pulse_async(self, color: str, duration: float = 1.0) -> None:
        self._assert_capability(Capability.SHINE)

        if duration < 0.5:
            logger.warning('TJBot cannot pulse for less than 0.5 seconds, using 0.5s')
            duration = 0.5
        if duration > 2.0:
            raise TJBotError('TJBot cannot pulse for more than 2.0 seconds')

        import colorsys

        num_steps = 20
        half_steps = num_steps // 2

        rgb_target = webcolors.hex_to_rgb(normalize_color(color))
        h, _l, s = colorsys.rgb_to_hls(
            rgb_target.red / 255.0,
            rgb_target.green / 255.0,
            rgb_target.blue / 255.0,
        )

        ramp_colors: List[str] = []
        for i in range(half_steps):
            l_val = (i / half_steps) * 0.5
            r, g, b = colorsys.hls_to_rgb(h, l_val, s)
            ramp_colors.append(
                webcolors.rgb_to_hex((int(r * 255), int(g * 255), int(b * 255)))
            )
        full_ramp = ramp_colors + ramp_colors[::-1]

        def _ease_in_out_quad(t: float, b: float, c: float, d: float) -> float:
            t /= d / 2
            if t < 1:
                return c / 2 * t * t + b
            t -= 1
            return -c / 2 * (t * (t - 2) - 1) + b

        ease_times = [
            _ease_in_out_quad(i, 0, 1, len(full_ramp)) * duration
            for i in range(len(full_ramp))
        ]

        prev_time = 0.0
        for i, c in enumerate(full_ramp):
            sleep_time = ease_times[i] - prev_time
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            await asyncio.to_thread(self.rpi_driver.render_led, c.lstrip('#'))
            prev_time = ease_times[i]

    def shine_colors(self) -> List[str]:
        if not self._shine_colors:
            try:
                self._shine_colors = get_shine_colors()
            except Exception:
                self._shine_colors = []
        return self._shine_colors

    def random_color(self) -> str:
        colors = self.shine_colors()
        if not colors:
            raise TJBotError("No named colors are available.")
        return random.choice(colors)

    # --- WAVE ---
    def arm_back(self):
        self._assert_capability(Capability.WAVE)
        self.rpi_driver.render_servo_position(ServoPosition.ARM_BACK)

    async def arm_back_async(self) -> None:
        await asyncio.to_thread(self.arm_back)

    def raise_arm(self):
        self._assert_capability(Capability.WAVE)
        self.rpi_driver.render_servo_position(ServoPosition.ARM_UP)

    async def raise_arm_async(self) -> None:
        await asyncio.to_thread(self.raise_arm)

    def lower_arm(self):
        self._assert_capability(Capability.WAVE)
        self.rpi_driver.render_servo_position(ServoPosition.ARM_DOWN)

    async def lower_arm_async(self) -> None:
        await asyncio.to_thread(self.lower_arm)

    def wave(self):
        self._assert_capability(Capability.WAVE)
        delay = 0.2
        self.rpi_driver.render_servo_position(ServoPosition.ARM_UP)
        time.sleep(delay)
        self.rpi_driver.render_servo_position(ServoPosition.ARM_DOWN)
        time.sleep(delay)
        self.rpi_driver.render_servo_position(ServoPosition.ARM_UP)

    async def wave_async(self) -> None:
        await asyncio.to_thread(self.wave)

    # --- SPEAK ---
    def speak(self, message: str):
        self._assert_capability(Capability.SPEAK)
        logger.info(f"TJBot speaking: '{message}'")
        self.rpi_driver.speak(message)

    async def speak_async(self, message: str) -> None:
        await asyncio.to_thread(self.speak, message)

    def play(self, sound_file: str):
        self.rpi_driver.play_audio(sound_file)

    async def play_async(self, sound_file: str) -> None:
        await asyncio.to_thread(self.play, sound_file)

    # --- LISTEN ---
    def listen(
        self,
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
    ) -> Union[str, None]:
        """
        Listen for speech.
        :param on_partial_result: Optional callback for partial transcript events.
        :param on_final_result: Optional callback for final transcript events.
        """
        self._assert_capability(Capability.LISTEN)

        listen_config = self.config.listen
        mode = infer_stt_mode(listen_config)

        local_cfg = listen_config.backend.local if (listen_config.backend and listen_config.backend.local) else None
        model_name = (local_cfg.model if local_cfg else None) or '<unknown>'

        if mode == 'streaming' and on_partial_result is None:
            raise TJBotError(
                f'STT model "{model_name}" is streaming. Call listen(on_partial_result, on_final_result) '
                f'so TJBot can deliver partial/final transcripts.'
            )

        if mode == 'offline' and on_partial_result is not None:
            raise TJBotError(
                f'STT model "{model_name}" is offline. Call listen() without a callback.'
            )

        if on_partial_result is not None or on_final_result is not None:
            self.rpi_driver.listen_for_transcript(on_final=on_final_result, on_partial=on_partial_result)
            return None

        result = self.rpi_driver.listen_for_transcript()
        logger.info(f'Heard: "{result}"')
        return result

    async def listen_async(
        self,
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
    ) -> Union[str, None]:
        self._assert_capability(Capability.LISTEN)

        listen_config = self.config.listen
        mode = infer_stt_mode(listen_config)

        local_cfg = listen_config.backend.local if (listen_config.backend and listen_config.backend.local) else None
        model_name = (local_cfg.model if local_cfg else None) or '<unknown>'

        if mode == 'streaming' and on_partial_result is None:
            raise TJBotError(
                f'STT model "{model_name}" is streaming. Call listen_async(on_partial_result, on_final_result) '
                f'so TJBot can deliver partial/final transcripts.'
            )

        if mode == 'offline' and on_partial_result is not None:
            raise TJBotError(
                f'STT model "{model_name}" is offline. Call listen_async() without a callback.'
            )

        if mode == 'streaming':
            loop = asyncio.get_running_loop()

            def _dispatch_callback(callback: Optional[Callable[[str], None]], text: str) -> None:
                if callback is None:
                    return

                if asyncio.iscoroutinefunction(callback):
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(callback(text)))
                else:
                    loop.call_soon_threadsafe(callback, text)

            def _partial_cb(text: str) -> None:
                _dispatch_callback(on_partial_result, text)

            def _final_cb(text: str) -> None:
                _dispatch_callback(on_final_result, text)

            await asyncio.to_thread(
                self.rpi_driver.listen_for_transcript,
                on_partial=_partial_cb,
                on_final=_final_cb,
            )
            return None

        result = await asyncio.to_thread(self.rpi_driver.listen_for_transcript)
        logger.info(f'Heard: "{result}"')
        return result

    # --- LOOK ---
    def look(self, file_path: Optional[str] = None) -> str:
        self._assert_capability(Capability.SEE)
        return self.rpi_driver.capture_photo(file_path)

    async def look_async(self, file_path: Optional[str] = None) -> str:
        return await asyncio.to_thread(self.look, file_path)

    def see(self) -> bytes:
        self._assert_capability(Capability.SEE)
        capture_buffer = getattr(self.rpi_driver, 'capture_photo_buffer', None)
        if callable(capture_buffer):
            return capture_buffer()

        photo_path = self.rpi_driver.capture_photo()
        try:
            with open(photo_path, "rb") as image_file:
                return image_file.read()
        finally:
            if os.path.exists(photo_path):
                os.remove(photo_path)

    async def see_async(self) -> bytes:
        return await asyncio.to_thread(self.see)

    def get_local_models(self, model_type: Optional[str] = None, installed_only: bool = True) -> List[str]:
        registry = ModelRegistry.get_instance()
        models = registry.lookup_models(model_type, installed_only)
        return [model.key for model in models]

    def detect_objects(self, image: Union[str, bytes]) -> List[Dict[str, Any]]:
        self._assert_capability(Capability.SEE)
        return self.rpi_driver.detect_objects(image)

    def classify_image(self, image: Union[str, bytes]) -> List[Dict[str, Any]]:
        self._assert_capability(Capability.SEE)
        return self.rpi_driver.classify_image(image)

    def detect_faces(self, image: Union[str, bytes]) -> Dict[str, Any]:
        self._assert_capability(Capability.SEE)
        return self.rpi_driver.detect_faces(image)

    def describe_image(self, image: Union[str, bytes]) -> Dict[str, Any]:
        self._assert_capability(Capability.SEE)
        return self.rpi_driver.describe_image(image)
