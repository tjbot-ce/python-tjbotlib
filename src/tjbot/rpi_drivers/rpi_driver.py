from abc import ABC, abstractmethod
from typing import Optional, Set, Any
import logging

from ..config.models import (
    SeeConfig,
    ListenConfig,
    SpeakConfig,
    WaveConfig,
    LEDCommonAnodeConfig,
    LEDNeopixelConfig
)
from ..utils import Capability, Hardware
from ..camera import CameraController
from ..microphone import MicrophoneController
from ..speaker import SpeakerController
from ..stt import STTController
from ..tts import TTSController
from ..error import TJBotError

logger = logging.getLogger(__name__)

class RPiHardwareDriver(ABC):
    """
    Abstract base class for Raspberry Pi Hardware Drivers.
    """

    # Capability Checks
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

    # Capabilities
    @abstractmethod
    def capture_photo(self, file_path: Optional[str] = None) -> str:
        pass

    @abstractmethod
    def render_led(self, hex_color: str) -> None:
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
    def listen_for_transcript(self, on_partial: Optional[Any] = None, on_final: Optional[Any] = None) -> str:
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

        # Config cache
        self.speak_config: Optional[SpeakConfig] = None
        self.listen_config: Optional[ListenConfig] = None

    def has_hardware(self, hardware: str) -> bool:
        return hardware in self.initialized_hardware

    def has_capability(self, capability: str) -> bool:
        if capability == Capability.LISTEN:
            return self.has_hardware(Hardware.MICROPHONE)
        elif capability == Capability.LOOK:
            return self.has_hardware(Hardware.CAMERA)
        elif capability == Capability.SHINE:
            return self.has_hardware(Hardware.LED_COMMON_ANODE) or self.has_hardware(Hardware.LED_NEOPIXEL)
        elif capability == Capability.SPEAK:
            return self.has_hardware(Hardware.SPEAKER)
        elif capability == Capability.WAVE:
            return self.has_hardware(Hardware.SERVO)
        return False

    def setup_camera(self, config: SeeConfig) -> None:
        self.camera_controller = CameraController()
        width = config.cameraResolution[0] if config.cameraResolution else 1920
        height = config.cameraResolution[1] if config.cameraResolution else 1080
        self.camera_controller.initialize(
            (width, height),
            config.verticalFlip or False,
            config.horizontalFlip or False
        )
        self.initialized_hardware.add(Hardware.CAMERA)

    def setup_microphone(self, config: ListenConfig) -> None:
        self.microphone_controller = MicrophoneController()
        self.listen_config = config

        rate = config.microphoneRate or 44100
        channels = config.microphoneChannels or 1 # ALSA default is often 1
        device = config.device or ''

        self.microphone_controller.initialize(rate, channels, device)
        self.stt_controller = STTController(config)
        self.initialized_hardware.add(Hardware.MICROPHONE)

    def setup_speaker(self, config: SpeakConfig) -> None:
        self.speaker_controller = SpeakerController()
        device = config.device or ''
        self.speak_config = config

        self.speaker_controller.initialize(device)
        self.speaker_controller.set_audio_lifecycle_callbacks(
            lambda: self.pause_mic(),
            lambda: self.resume_mic()
        )

        self.tts_controller = TTSController(self.speaker_controller)
        self.initialized_hardware.add(Hardware.SPEAKER)

    def capture_photo(self, file_path: Optional[str] = None) -> str:
        if not self.camera_controller:
             raise TJBotError("Camera not initialized.")
        return self.camera_controller.capture_photo(file_path)

    def play_audio(self, file_path: str) -> None:
        if not self.speaker_controller:
            raise TJBotError("Speaker not initialized.")
        self.speaker_controller.play_audio(file_path)

    def speak(self, message: str) -> None:
        if not self.tts_controller or not self.speak_config:
            raise TJBotError("TTS controller not initialized.")
        self.tts_controller.speak(message, self.speak_config)

    def listen_for_transcript(self, on_partial: Optional[Any] = None, on_final: Optional[Any] = None) -> str:
        if not self.stt_controller or not self.microphone_controller:
            raise TJBotError("STT controller not initialized.")

        stream = self.microphone_controller.get_input_stream()
        return self.stt_controller.transcribe(stream, on_partial_result=on_partial, on_final_result=on_final)

    def pause_mic(self) -> None:
        if self.microphone_controller:
            self.microphone_controller.pause()

    def resume_mic(self) -> None:
        if self.microphone_controller:
            self.microphone_controller.resume()

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
