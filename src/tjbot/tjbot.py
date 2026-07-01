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

import asyncio
import atexit
import os
import random
import re
import signal
import threading
from importlib.metadata import version, PackageNotFoundError
from typing import Optional, Dict, Any, List, Union, Callable, cast

from .config import TJBotConfig
from .utils.errors import TJBotError
from .utils import (
    Hardware,
    Capability,
    ModelRegistry,
    ModelType,
    get_logger,
    get_shine_colors,
    init_logging,
    normalize_color,
    sleep as tjbot_sleep_async,
    sleep_sync as tjbot_sleep,
    set_log_level,
)
from .utils.logging import TJBotLogLevel, log_silly
from .servo import ServoPosition
from .rpi_drivers import (
    RPiHardwareDriver,
    RPi3Driver,
    RPi4Driver,
    RPi5Driver,
    RPiDetect,
)
from .stt.stt_utils import infer_stt_mode

init_logging("info")
logger = get_logger(__name__)


_CAPABILITY_HARDWARE_MAP: Dict[str, str] = {
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

    try:
        _pkg_version = version("tjbot-ce")
    except PackageNotFoundError:
        _pkg_version = "0.0.0"
    VERSION = f"v{_pkg_version}"
    Hardware = Hardware
    _instance: Optional["TJBot"] = None

    def __init__(
        self,
        override_config: Optional[Dict[str, Any]] = None,
        recipe_config_path: str = "recipe.toml",
        auto_initialize: bool = True,
    ):
        # Register as singleton if no instance exists yet
        if TJBot._instance is None:
            TJBot._instance = self

        self._override_config = override_config
        self._recipe_config_path = recipe_config_path
        self.config: Optional[TJBotConfig] = None

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
            self._initialize(override_config, recipe_config_path)
        else:
            # Lazy initialization: config will be loaded on first initialize() call
            pass

    @classmethod
    def get_instance(cls) -> "TJBot":
        """Return the singleton TJBot instance, creating an uninitialized one if needed.
        Call ``initialize()`` before using any TJBot capabilities."""
        if cls._instance is None:
            cls._instance = cls(auto_initialize=False)
        return cls._instance

    @classmethod
    def get_recipe_config(
        cls, recipe_config_path: str = "recipe.toml"
    ) -> Dict[str, Any]:
        config = TJBotConfig(recipe_config_path=recipe_config_path)
        return config.recipe

    def initialize(
        self,
        override_config: Optional[Dict[str, Any]] = None,
        recipe_config_path: str = "recipe.toml",
    ) -> "TJBot":
        self._initialize(override_config, recipe_config_path)
        return self

    def _initialize(
        self,
        override_config: Optional[Dict[str, Any]] = None,
        recipe_config_path: str = "recipe.toml",
    ) -> None:
        self._install_process_cleanup_hooks()

        if self._initialized:
            self.cleanup()

        # Load config if not already loaded (supports lazy initialization)
        if self.config is None:
            self.config = TJBotConfig(override_config, recipe_config_path)
        else:
            # Reload if explicit parameters passed
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

                if (
                    self._cleanup_completed_run_id == wait_run_id
                    and self._cleanup_error is not None
                ):
                    raise TJBotError(
                        "Failed to clean up TJBot resources", cause=self._cleanup_error
                    )
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
            cleanup_error = (
                error if isinstance(error, Exception) else Exception(str(error))
            )
            raise TJBotError("Failed to clean up TJBot resources", cause=cleanup_error)
        finally:
            with self._cleanup_condition:
                self._cleanup_in_progress = False
                self._cleanup_completed_run_id = run_id
                self._cleanup_error = cleanup_error
                self._cleanup_condition.notify_all()

    _CLEANUP_TIMEOUT_S = 3.0

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

            def _handler(signum, frame, prev=previous, _sig_name=sig_name):
                _ = frame
                exit_code = {"SIGINT": 130, "SIGTERM": 143, "SIGHUP": 129}.get(
                    _sig_name, 1
                )
                self._run_lifecycle_cleanup(exit_code=exit_code)
                if callable(prev):
                    prev(signum, frame)

            signal.signal(sig, _handler)

        self._process_hooks_installed = True

    def _run_lifecycle_cleanup(self, exit_code: Optional[int] = None) -> None:
        """
        Best-effort cleanup path used by process lifecycle hooks.

        When called from a signal handler (exit_code is set), cleanup runs in a
        background thread and is given at most _CLEANUP_TIMEOUT_S seconds before
        the process is force-exited — matching Node's Promise.race approach.

        When called from atexit (exit_code is None), cleanup runs inline so the
        process drains fully before exiting.
        """
        if exit_code is None:
            # atexit: run inline, best-effort
            try:
                self.cleanup()
            except Exception as error:
                logger.warning("TJBot lifecycle cleanup failed: %s", error)
            return

        # Signal path: run cleanup in a thread with a hard timeout
        cleanup_done = threading.Event()

        def _do_cleanup():
            try:
                self.cleanup()
            except Exception as error:
                logger.warning("TJBot lifecycle cleanup failed: %s", error)
            finally:
                cleanup_done.set()

        t = threading.Thread(target=_do_cleanup, daemon=True)
        t.start()
        cleanup_done.wait(timeout=self._CLEANUP_TIMEOUT_S)
        raise SystemExit(exit_code)

    def _initialize_hardware_from_config(self):
        if self.rpi_driver is None:
            return
        config = self.config
        if config is None:
            return

        hw_config = config.hardware
        enabled_hardware: List[str] = []

        # Determine what to init
        if hw_config.speaker:
            enabled_hardware.append(Hardware.SPEAKER)
        if hw_config.microphone:
            enabled_hardware.append(Hardware.MICROPHONE)
        if hw_config.camera:
            enabled_hardware.append(Hardware.CAMERA)
        if (
            getattr(hw_config, "led", False)
            or getattr(hw_config, "led_neopixel", False)
            or getattr(hw_config, "led_common_anode", False)
        ):
            enabled_hardware.append(Hardware.LED)
        if hw_config.servo:
            enabled_hardware.append(Hardware.SERVO)

        if not enabled_hardware:
            logger.debug("No hardware configured in config file")
            return

        logger.info(f"Initializing TJBot with {', '.join(enabled_hardware)}")

        for hw in enabled_hardware:
            if hw == Hardware.CAMERA:
                self.rpi_driver.setup_camera(config.see)
            elif hw == Hardware.LED:
                shine_config = config.shine
                has_neopixel = bool(
                    (
                        getattr(shine_config, "has_neopixel_led", False)
                        if shine_config
                        else False
                    )
                    or getattr(hw_config, "led_neopixel", False)
                )
                has_common_anode = bool(
                    (
                        getattr(shine_config, "has_common_anode_led", False)
                        if shine_config
                        else False
                    )
                    or getattr(hw_config, "led_common_anode", False)
                )

                if not has_neopixel and not has_common_anode:
                    raise TJBotError(
                        "LED hardware enabled but no LED type configured. Set shine.hasNeopixelLED or "
                        "shine.hasCommonAnodeLED to true in your tjbot configuration file (~/.tjbot/tjbot.toml)."
                    )

                if has_neopixel:
                    neopixel = shine_config.neopixel
                    if not neopixel or (
                        neopixel.gpio_pin is None and not neopixel.spi_interface
                    ):
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
                self.rpi_driver.setup_microphone(config.listen)
            elif hw == Hardware.SERVO:
                self.rpi_driver.setup_servo(config.wave)
            elif hw == Hardware.SPEAKER:
                self.rpi_driver.setup_speaker(config.speak)

    def _assert_capability(self, capability: str) -> RPiHardwareDriver:
        logger.debug("Asserting capability: %s", capability)
        if self.config is None:
            raise TJBotError(
                "TJBot has not been initialized. Call initialize() before using TJBot methods."
            )
        if not self._initialized or self.rpi_driver is None:
            raise TJBotError(
                "TJBot has not been initialized. Call initialize() before using TJBot methods."
            )
        if not self.rpi_driver.has_capability(capability):
            required_hardware = _CAPABILITY_HARDWARE_MAP.get(capability)
            if required_hardware:
                raise TJBotError(
                    f"TJBot is not configured to {capability}. Required hardware: {required_hardware}."
                )
            raise TJBotError(f"TJBot is not configured to {capability}.")

        capabilities = ", ".join(sorted(self.rpi_driver.get_hardware()))
        log_silly(logger, "TJBot capabilities: %s", capabilities)
        return self.rpi_driver

    def set_log_level(self, level: TJBotLogLevel) -> None:
        set_log_level(level)

    async def sleep(self, sec: float) -> None:
        await tjbot_sleep_async(sec)

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
        if c.startswith("#"):
            c = c[1:]

        # Async in Node? Node `shine` is async. Python usually sync unless using asyncio.
        # RPi driver `render_led` is sync.
        driver = self.rpi_driver
        if driver is None:
            raise TJBotError(
                "TJBot has not been initialized. Call initialize() before using TJBot methods."
            )
        driver.render_led(c)

    def pulse(self, color: str, duration: float = 1.0) -> None:
        """
        Pulse the LED a single time.
        """
        self._assert_capability(Capability.SHINE)

        if duration < 0.5:
            logger.warning(
                "TJBot cannot pulse for less than 0.5 seconds, using duration of 0.5 seconds"
            )
            duration = 0.5
        if duration > 2.0:
            logger.warning(
                "TJBot cannot pulse for more than 2 seconds, using duration of 2.0 seconds"
            )
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

        import colorsys
        import webcolors

        rgb_target = webcolors.hex_to_rgb(normalize_color(color))  # (r, g, b)
        # Convert to HLS (Hue, Lightness, Saturation)
        h, lightness, s = colorsys.rgb_to_hls(
            rgb_target.red / 255.0, rgb_target.green / 255.0, rgb_target.blue / 255.0
        )

        # We want to ramp L from 0 to 0.5 (or target L?)
        # Node code: `l = 0.0 + (i / (numSteps / 2)) * 0.5;`
        # This implies it peaks at L=0.5. If the color is lighter than 0.5, it might look weird?
        # Assuming standard LED behavior, max brightness is usually decent.

        ramp_colors = []
        half_steps = int(num_steps / 2)
        for i in range(half_steps):
            l_val = (i / half_steps) * 0.5
            r, g, b = colorsys.hls_to_rgb(h, l_val, s)
            ramp_colors.append(
                webcolors.rgb_to_hex((int(r * 255), int(g * 255), int(b * 255)))
            )

        # Full ramp: up + down
        full_ramp = ramp_colors + ramp_colors[::-1]
        log_silly(logger, "color ramp for pulse: %s", ", ".join(ramp_colors))

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
                tjbot_sleep(sleep_time)

            # Render
            if c.startswith("#"):
                c = c[1:]
            log_silly(logger, "pulse step %d: setting color to %s", i, c)
            self.rpi_driver.render_led(c)  # type: ignore[union-attr]
            prev_time = target_time

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
        driver = self._assert_capability(Capability.WAVE)
        driver.render_servo_position(ServoPosition.ARM_BACK)

    def raise_arm(self):
        driver = self._assert_capability(Capability.WAVE)
        driver.render_servo_position(ServoPosition.ARM_UP)

    def lower_arm(self):
        driver = self._assert_capability(Capability.WAVE)
        driver.render_servo_position(ServoPosition.ARM_DOWN)

    def wave(self):
        driver = self._assert_capability(Capability.WAVE)
        delay = 0.2
        driver.render_servo_position(ServoPosition.ARM_UP)
        tjbot_sleep(delay)
        driver.render_servo_position(ServoPosition.ARM_DOWN)
        tjbot_sleep(delay)
        driver.render_servo_position(ServoPosition.ARM_UP)
        tjbot_sleep(delay)

    # --- SPEAK ---
    def speak(self, message: str):
        driver = self._assert_capability(Capability.SPEAK)

        logger.info(f"TJBot speaking: '{message}'")

        # silently change "tjbot" to "t j bot" so that TTS engines pronounce it correctly
        tjbot_pattern = re.compile(r"\btjbot\b", re.IGNORECASE)
        normalized_message = tjbot_pattern.sub("t j bot", message)

        driver.speak(normalized_message)

    def play(self, sound_file: str):
        """Play an audio file.

        :param sound_file: Path to the audio file to play.
        :raises TJBotError: If TJBot has not been initialized.
        """
        if self.rpi_driver is None:
            raise TJBotError(
                "TJBot has not been initialized. Call initialize() before using TJBot methods."
            )
        self.rpi_driver.play_audio(sound_file)

    # --- LISTEN ---
    def listen(self, timeout: Optional[float] = None) -> str:
        """
        Listen for speech.

        Args:
            timeout: Optional timeout in seconds. If speech is not detected within this
                time, a TJBotError is raised.

        Returns:
            The final transcript from the microphone.

        Raises:
            TJBotError: If TJBot is not initialized or the configured STT mode is streaming.
        """
        driver = self._assert_capability(Capability.LISTEN)

        config = self.config
        if config is None:
            raise TJBotError(
                "TJBot has not been initialized. Call initialize() before using TJBot methods."
            )

        listen_config = config.listen
        mode = infer_stt_mode(listen_config)

        local_cfg = (
            listen_config.backend.local
            if (listen_config.backend and listen_config.backend.local)
            else None
        )
        if mode == "streaming":
            model_name = (local_cfg.model if local_cfg else None) or "<unknown>"
            raise TJBotError(
                f'STT model "{model_name}" is streaming. Call listen_async(on_partial_result, on_final_result) '
                f"to receive partial/final transcript callbacks."
            )

        if timeout is not None:
            abort_event = threading.Event()
            timer = threading.Timer(timeout, abort_event.set)
            timer.start()
            try:
                result = driver.listen_for_transcript(abort_signal=abort_event)
            finally:
                timer.cancel()
        else:
            result = driver.listen_for_transcript()

        logger.info(f'Heard: "{result}"')
        return result

    async def listen_async(
        self,
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Listen for speech asynchronously with optional callbacks for partial/final results.

        Args:
            on_partial_result: Callback invoked with each partial transcript.
            on_final_result: Callback invoked with the final transcript.
            timeout: Optional timeout in seconds. If speech is not detected within this
                time, a TJBotError is raised.
        """
        driver = self._assert_capability(Capability.LISTEN)

        config = self.config
        if config is None:
            raise TJBotError(
                "TJBot has not been initialized. Call initialize() before using TJBot methods."
            )

        listen_config = config.listen
        mode = infer_stt_mode(listen_config)

        if on_partial_result is None and on_final_result is None:
            raise TJBotError(
                "listen_async() requires at least one callback. Use listen() for synchronous final transcript mode."
            )

        abort_event = threading.Event() if timeout is not None else None
        timer = (
            threading.Timer(timeout, abort_event.set)
            if timeout is not None and abort_event is not None
            else None
        )
        if timer is not None:
            timer.start()

        try:
            if mode == "streaming":
                loop = asyncio.get_running_loop()

                def _dispatch_callback(
                    callback: Optional[Callable[[str], None]], text: str
                ) -> None:
                    if callback is None:
                        return

                    if asyncio.iscoroutinefunction(callback):
                        loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(callback(text))
                        )
                    else:
                        loop.call_soon_threadsafe(callback, text)

                def _partial_cb(text: str) -> None:
                    _dispatch_callback(on_partial_result, text)

                def _final_cb(text: str) -> None:
                    _dispatch_callback(on_final_result, text)

                await asyncio.to_thread(
                    driver.listen_for_transcript,
                    on_partial=_partial_cb,
                    on_final=_final_cb,
                    abort_signal=abort_event,
                )
                return

            result = await asyncio.to_thread(
                driver.listen_for_transcript, abort_signal=abort_event
            )
            logger.info(f'Heard: "{result}"')
            if on_final_result is not None:
                on_final_result(result)
        finally:
            if timer is not None:
                timer.cancel()

    # --- LOOK ---
    def look(self, file_path: Optional[str] = None) -> str:
        driver = self._assert_capability(Capability.SEE)
        return driver.capture_photo(file_path)

    def see(self) -> bytes:
        driver = self._assert_capability(Capability.SEE)
        capture_buffer = getattr(driver, "capture_photo_buffer", None)
        if callable(capture_buffer):
            try:
                return cast(bytes, capture_buffer())
            except Exception:
                pass

        photo_path = driver.capture_photo()
        try:
            with open(photo_path, "rb") as image_file:
                return image_file.read()
        finally:
            if os.path.exists(photo_path):
                os.remove(photo_path)

    def get_local_models(
        self, model_type: Optional[ModelType] = None, installed_only: bool = True
    ) -> List[str]:
        registry = ModelRegistry.get_instance()
        models = registry.lookup_models(model_type, installed_only)
        return [model.key for model in models]

    def detect_objects(self, image: Union[str, bytes]) -> List[Dict[str, Any]]:
        driver = self._assert_capability(Capability.SEE)
        return driver.detect_objects(image)

    def classify_image(self, image: Union[str, bytes]) -> List[Dict[str, Any]]:
        driver = self._assert_capability(Capability.SEE)
        return driver.classify_image(image)

    def detect_faces(self, image: Union[str, bytes]) -> Dict[str, Any]:
        driver = self._assert_capability(Capability.SEE)
        return driver.detect_faces(image)

    def describe_image(self, image: Union[str, bytes]) -> Dict[str, Any]:
        driver = self._assert_capability(Capability.SEE)
        return driver.describe_image(image)
