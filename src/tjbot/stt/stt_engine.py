from abc import ABC, abstractmethod
from typing import Any, Callable, Iterator, Optional, TypedDict

from ..config.config_types import ListenConfig, STTEngineConfig
from ..utils.errors import TJBotError


class STTRequestOptions(TypedDict, total=False):
    on_partial_result: Callable[[str], None]
    on_final_result: Callable[[str], None]
    abort_signal: Any


class STTEngine(ABC):
    """Abstract base class for speech-to-text engines."""

    def __init__(self, config: Optional[STTEngineConfig] = None):
        self.config = config or {}

    @abstractmethod
    def initialize(self, microphone_rate: int, microphone_channels: int) -> None:
        pass

    def cleanup(self) -> None:
        pass

    @abstractmethod
    def transcribe(self, audio_stream: Iterator[bytes], options: Optional[STTRequestOptions] = None) -> str:
        pass

    def ensure_stream(self, stream: Optional[Iterator[bytes]]) -> Iterator[bytes]:
        if stream is None:
            raise TJBotError("Microphone stream is not available")
        return stream

    def _is_abort_signal_set(self, abort_signal: Any) -> bool:
        if abort_signal is None:
            return False

        is_set_fn = getattr(abort_signal, "is_set", None)
        if callable(is_set_fn):
            try:
                return bool(is_set_fn())
            except Exception:
                return False

        aborted = getattr(abort_signal, "aborted", None)
        if isinstance(aborted, bool):
            return aborted

        return False

    def is_aborted(self, options: Optional[STTRequestOptions] = None) -> bool:
        options = options or {}
        abort_signal = options.get("abort_signal")
        return self._is_abort_signal_set(abort_signal)

    def raise_if_aborted(self, options: Optional[STTRequestOptions] = None) -> None:
        if self.is_aborted(options):
            raise TJBotError("STT transcription was aborted.", code="stt.aborted")


def create_stt_engine(listen_config: ListenConfig) -> STTEngine:
    backend_config = listen_config.backend
    backend_type = backend_config.type if backend_config else "local"

    try:
        if backend_type == "none":
            class NoneSTTEngine(STTEngine):
                def initialize(self, microphone_rate: int, microphone_channels: int) -> None:
                    _ = microphone_rate
                    _ = microphone_channels

                def transcribe(self, audio_stream: Iterator[bytes], options: Optional[STTRequestOptions] = None) -> str:
                    _ = audio_stream
                    _ = options
                    raise TJBotError(
                        "STT is disabled. Configure a speech-to-text backend (local, ibm-watson-stt, google-cloud-stt, or azure-stt) to use speech recognition."
                    )

            return NoneSTTEngine({})

        if backend_type == "local":
            from .backends.sherpa_onnx_stt import SherpaONNXSTTEngine

            cfg = backend_config.local if backend_config else None
            return SherpaONNXSTTEngine(cfg)

        if backend_type == "ibm-watson-stt":
            from .backends.watson_stt import IBMWatsonSTTEngine

            cfg = backend_config.ibm_watson_stt if backend_config else None
            return IBMWatsonSTTEngine(cfg)

        if backend_type == "google-cloud-stt":
            from .backends.google_cloud_stt import GoogleCloudSTTEngine

            cfg = backend_config.google_cloud_stt if backend_config else None
            return GoogleCloudSTTEngine(cfg)

        if backend_type == "azure-stt":
            from .backends.azure_stt import AzureSTTEngine

            cfg = backend_config.azure_stt if backend_config else None
            return AzureSTTEngine(cfg)

        raise TJBotError(f"Unknown STT backend type: {backend_type}")
    except Exception as error:
        raise TJBotError(f'Failed to load STT backend "{backend_type}". Ensure dependencies are installed.', cause=error)
