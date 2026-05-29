from abc import ABC, abstractmethod
from typing import Optional, Set, Any
import logging

from ..config.config_types import (
    SeeConfig,
    ListenConfig,
    ShineConfig,
    SpeakConfig,
    WaveConfig,
    LEDCommonAnodeConfig,
    LEDNeopixelConfig,
)
from ..utils import Capability, Hardware, is_command_available
from ..camera import CameraController
from ..microphone import MicrophoneController
from ..speaker import SpeakerController
from ..stt import STTController
from ..tts import TTSController
from ..vision import VisionController
from ..utils.errors import TJBotError

logger = logging.getLogger(__name__)


class RPiHardwareDriver(ABC):
    """
    Abstract base class for Raspberry Pi Hardware Drivers.
    """

    # Capability Checks
    @abstractmethod
    def get_hardware(self) -> Set[str]:
        pass

    @abstractmethod
    def has_hardware(self, hardware: str) -> bool:
        pass

    @abstractmethod
    def has_capability(self, capability: str) -> bool:
        pass

    # Setup
    @abstractmethod
    def setup_camera(self, config: SeeConfig) -> None:
        pass

    @abstractmethod
    def setup_led(self, config: ShineConfig) -> None:
        pass

    @abstractmethod
    def setup_led_common_anode(self, config: LEDCommonAnodeConfig) -> None:
        pass

    @abstractmethod
    def setup_led_neopixel(self, config: LEDNeopixelConfig) -> None:
        pass

    @abstractmethod
    def setup_microphone(self, config: ListenConfig) -> None:
        pass

    @abstractmethod
    def setup_servo(self, config: WaveConfig) -> None:
        pass

    @abstractmethod
    def setup_speaker(self, config: SpeakConfig) -> None:
        pass

    @abstractmethod
    def cleanup(self) -> None:
        pass

    @abstractmethod
    def initialize_stt_engine(self) -> None:
        pass

    @abstractmethod
    def initialize_tts_engine(self) -> None:
        pass

    @abstractmethod
    def initialize_vision_engine(self) -> None:
        pass

    @abstractmethod
    def start_mic(self) -> None:
        pass

    @abstractmethod
    def pause_mic(self) -> None:
        pass

    @abstractmethod
    def resume_mic(self) -> None:
        pass

    @abstractmethod
    def stop_mic(self) -> None:
        pass

    @abstractmethod
    def get_mic_input_stream(self) -> Any:
        pass

    # Capabilities
    @abstractmethod
    def capture_photo(self, file_path: Optional[str] = None) -> str:
        pass

    @abstractmethod
    def capture_photo_buffer(self) -> bytes:
        pass

    @abstractmethod
    def render_led(self, hex_color: str) -> None:
        pass

    @abstractmethod
    def render_led_common_anode(self, rgb_color: tuple[int, int, int]) -> None:
        pass

    @abstractmethod
    def render_led_neopixel(self, hex_color: str) -> None:
        pass

    @abstractmethod
    def render_servo_position(self, position: int) -> None:
        pass

    @abstractmethod
    def play_audio(self, file_path: str) -> None:
        pass

    @abstractmethod
    def speak(self, message: str) -> None:
        pass

    @abstractmethod
    def listen_for_transcript(
        self, on_partial: Optional[Any] = None, on_final: Optional[Any] = None
    ) -> str:
        pass

    @abstractmethod
    def detect_objects(self, image: Any) -> Any:
        pass

    @abstractmethod
    def classify_image(self, image: Any) -> Any:
        pass

    @abstractmethod
    def detect_faces(self, image: Any) -> Any:
        pass

    @abstractmethod
    def describe_image(self, image: Any) -> Any:
        pass


class RPiBaseHardwareDriver(RPiHardwareDriver):
    """
    Base implementation of RPi Hardware Driver.
    """

    def __init__(self):
        self.initialized_hardware: Set[str] = set()

        # Controllers
        self.camera_controller: Optional[CameraController] = None
        self.microphone_controller: Optional[MicrophoneController] = None
        self.speaker_controller: Optional[SpeakerController] = None
        self.stt_controller: Optional[STTController] = None
        self.tts_controller: Optional[TTSController] = None
        self.vision_controller: Optional[VisionController] = None

        # Config cache
        self.listen_config: Optional[ListenConfig] = None
        self.see_config: Optional[SeeConfig] = None
        self.shine_config: Optional[ShineConfig] = None
        self.speak_config: Optional[SpeakConfig] = None

    def has_hardware(self, hardware: str) -> bool:
        return hardware in self.initialized_hardware

    def get_hardware(self) -> Set[str]:
        return set(self.initialized_hardware)

    def has_capability(self, capability: str) -> bool:
        if capability == Capability.LISTEN:
            return self.has_hardware(Hardware.MICROPHONE)
        elif capability == Capability.SEE:
            return self.has_hardware(Hardware.CAMERA)
        elif capability == Capability.SHINE:
            return self.has_hardware(Hardware.LED)
        elif capability == Capability.SPEAK:
            return self.has_hardware(Hardware.SPEAKER)
        elif capability == Capability.WAVE:
            return self.has_hardware(Hardware.SERVO)
        return False

    def setup_camera(self, config: SeeConfig) -> None:
        self.camera_controller = CameraController()
        self.see_config = config
        width = config.camera_resolution[0] if config.camera_resolution else 1920
        height = config.camera_resolution[1] if config.camera_resolution else 1080
        capture_timeout = (
            config.capture_timeout if config.capture_timeout is not None else 500
        )
        zero_shutter_lag = (
            config.zero_shutter_lag if config.zero_shutter_lag is not None else False
        )
        self.camera_controller.initialize(
            (width, height),
            config.vertical_flip or False,
            config.horizontal_flip or False,
            capture_timeout,
            zero_shutter_lag,
        )
        self.initialized_hardware.add(Hardware.CAMERA)

    def setup_microphone(self, config: ListenConfig) -> None:
        self.microphone_controller = MicrophoneController()
        self.listen_config = config

        rate = config.microphone_rate or 44100
        channels = config.microphone_channels or 2
        device = config.device or ""

        self.microphone_controller.initialize(rate, channels, device)
        self.initialized_hardware.add(Hardware.MICROPHONE)

    def setup_led(self, config: ShineConfig) -> None:
        self.shine_config = config
        if config.has_common_anode_led:
            self.setup_led_common_anode(config.common_anode or LEDCommonAnodeConfig())
        if config.has_neopixel_led:
            self.setup_led_neopixel(config.neopixel or LEDNeopixelConfig())

    def setup_speaker(self, config: SpeakConfig) -> None:
        self.speaker_controller = SpeakerController()
        self.speak_config = config
        device = config.device or ""

        if not is_command_available("aplay"):
            raise TJBotError(
                "TJBot requires the aplay command for audio playback. "
                "Install it with: sudo apt-get install alsa-utils"
            )

        self.speaker_controller.initialize(device)
        self.speaker_controller.set_audio_lifecycle_callbacks(
            lambda: self.pause_mic(), lambda: self.resume_mic()
        )
        self.initialized_hardware.add(Hardware.SPEAKER)

    def initialize_stt_engine(self) -> None:
        if self.microphone_controller is None:
            raise TJBotError(
                "Microphone controller not initialized. Call setup_microphone() before initializing STT."
            )
        self.stt_controller = STTController(
            microphone_controller=self.microphone_controller
        )
        self.stt_controller.initialize(self.listen_config or ListenConfig())

    def initialize_tts_engine(self) -> None:
        if self.speaker_controller is None:
            raise TJBotError(
                "Speaker controller not initialized. Call setup_speaker() before initializing TTS."
            )
        self.tts_controller = TTSController(self.speaker_controller)
        self.tts_controller.initialize(self.speak_config or SpeakConfig())

    def initialize_vision_engine(self) -> None:
        self.vision_controller = VisionController()
        self.vision_controller.initialize(self.see_config or SeeConfig())

    def capture_photo(self, file_path: Optional[str] = None) -> str:
        if not self.camera_controller:
            raise TJBotError("Camera not initialized.")
        return self.camera_controller.capture_photo(file_path)

    def capture_photo_buffer(self) -> bytes:
        if not self.camera_controller:
            raise TJBotError("Camera not initialized.")
        return self.camera_controller.capture_photo_buffer()

    def detect_objects(self, image: Any) -> Any:
        if self.vision_controller is None:
            raise TJBotError(
                "Vision controller is not initialized. Call setup_camera() before using vision."
            )
        return self.vision_controller.detect_objects(image)

    def classify_image(self, image: Any) -> Any:
        if self.vision_controller is None:
            raise TJBotError(
                "Vision controller is not initialized. Call setup_camera() before using vision."
            )
        return self.vision_controller.classify_image(image)

    def detect_faces(self, image: Any) -> Any:
        if self.vision_controller is None:
            raise TJBotError(
                "Vision controller is not initialized. Call setup_camera() before using vision."
            )
        return self.vision_controller.detect_faces(image)

    def describe_image(self, image: Any) -> Any:
        if self.vision_controller is None:
            raise TJBotError(
                "Vision controller is not initialized. Call setup_camera() before using vision."
            )
        return self.vision_controller.describe_image(image)

    def play_audio(self, file_path: str) -> None:
        if not self.speaker_controller:
            raise TJBotError("Speaker not initialized.")
        self.speaker_controller.play_audio(file_path)

    def speak(self, message: str) -> None:
        if self.tts_controller is None:
            raise TJBotError(
                "TTS controller not initialized. Call setup_speaker() before speaking."
            )
        self.tts_controller.speak(message)

    def listen_for_transcript(
        self, on_partial: Optional[Any] = None, on_final: Optional[Any] = None
    ) -> str:
        if self.stt_controller is None:
            raise TJBotError(
                "STT controller not initialized. Call setup_microphone() before listening."
            )

        return self.stt_controller.transcribe(
            on_partial_result=on_partial,
            on_final_result=on_final,
        ).strip()

    def start_mic(self) -> None:
        if self.microphone_controller is None:
            raise TJBotError(
                "Microphone controller not initialized. Call setup_microphone() before starting microphone."
            )
        self.microphone_controller.start()

    def pause_mic(self) -> None:
        if self.microphone_controller:
            self.microphone_controller.pause()

    def resume_mic(self) -> None:
        if self.microphone_controller:
            self.microphone_controller.resume()

    def stop_mic(self) -> None:
        if self.microphone_controller is None:
            raise TJBotError(
                "Microphone controller not initialized. Call setup_microphone() before stopping microphone."
            )
        self.microphone_controller.stop()

    def get_mic_input_stream(self) -> Any:
        if self.microphone_controller is None:
            raise TJBotError(
                "Microphone controller not initialized. Call setup_microphone() before accessing stream."
            )
        return self.microphone_controller.get_input_stream()

    def cleanup(self) -> None:
        """Clean up all controllers and reset hardware state."""
        for controller_attr in (
            "camera_controller",
            "microphone_controller",
            "speaker_controller",
            "stt_controller",
            "tts_controller",
            "vision_controller",
        ):
            controller = getattr(self, controller_attr, None)
            if controller is not None:
                cleanup_fn = getattr(controller, "cleanup", None)
                if callable(cleanup_fn):
                    try:
                        cleanup_fn()
                    except Exception:
                        pass
                setattr(self, controller_attr, None)

        self.initialized_hardware.clear()

    # Abstract methods to be implemented by RPi version specific logic
    @abstractmethod
    def setup_led_common_anode(self, config: LEDCommonAnodeConfig) -> None:
        pass

    @abstractmethod
    def setup_led_neopixel(self, config: LEDNeopixelConfig) -> None:
        pass

    @abstractmethod
    def setup_servo(self, config: WaveConfig) -> None:
        pass

    @abstractmethod
    def render_led(self, hex_color: str) -> None:
        pass

    @abstractmethod
    def render_servo_position(self, position: int) -> None:
        pass
