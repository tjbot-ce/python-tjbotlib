from pathlib import Path
from typing import Iterable, Callable, Optional, Any
import logging
import numpy as np

from ..stt_engine import STTEngine, STTRequestOptions
from ...utils.errors import TJBotError
from ...utils.sherpa_runtime import load_sherpa_onnx_module

sherpa_onnx: Any = None

logger = logging.getLogger(__name__)


def _model_paths(key: str, model_dir: Path) -> dict:
    """Return the file paths for a given model key, mirroring node pathsForModelKey."""
    if key.startswith("moonshine"):
        return {
            "kind": "offline-moonshine",
            "preprocessor": str(model_dir / "preprocess.onnx"),
            "encoder": str(model_dir / "encode.int8.onnx"),
            "uncached_decoder": str(model_dir / "uncached_decode.int8.onnx"),
            "cached_decoder": str(model_dir / "cached_decode.int8.onnx"),
            "tokens": str(model_dir / "tokens.txt"),
        }
    if key == "whisper-tiny":
        return {
            "kind": "offline-whisper",
            "encoder": str(model_dir / "tiny.en-encoder.int8.onnx"),
            "decoder": str(model_dir / "tiny.en-decoder.int8.onnx"),
            "tokens": str(model_dir / "tiny.en-tokens.txt"),
        }
    if key == "whisper-base":
        return {
            "kind": "offline-whisper",
            "encoder": str(model_dir / "base.en-encoder.int8.onnx"),
            "decoder": str(model_dir / "base.en-decoder.int8.onnx"),
            "tokens": str(model_dir / "base.en-tokens.txt"),
        }
    if key == "zipformer-en":
        return {
            "kind": "streaming-zipformer",
            "encoder": str(
                model_dir / "encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
            ),
            "decoder": str(model_dir / "decoder-epoch-99-avg-1-chunk-16-left-128.onnx"),
            "joiner": str(
                model_dir / "joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
            ),
            "tokens": str(model_dir / "tokens.txt"),
        }
    if key == "paraformer-en":
        return {
            "kind": "streaming-paraformer",
            "encoder": str(model_dir / "encoder.int8.onnx"),
            "decoder": str(model_dir / "decoder.int8.onnx"),
            "tokens": str(model_dir / "tokens.txt"),
        }
    raise TJBotError(f"Unsupported STT model key: {key}")


class SherpaONNXSTTEngine(STTEngine):
    """Sherpa-ONNX (Local) Speech-to-Text backend."""

    def __init__(self, config: Optional[Any] = None):
        super().__init__(config or {})
        self.backend_config = config
        self.recognizer: Any = None
        self._model_kind: Optional[str] = None
        self._vad_path: Optional[str] = None
        self.microphone_rate = 16000
        self.microphone_channels = 1

    def initialize(self, microphone_rate: int, microphone_channels: int) -> None:
        self.microphone_rate = microphone_rate
        self.microphone_channels = microphone_channels

        global sherpa_onnx

        if sherpa_onnx is None:
            try:
                sherpa_onnx = load_sherpa_onnx_module()
            except Exception as error:
                raise TJBotError(
                    "sherpa-onnx library is unavailable. Ensure the package is installed and "
                    "LD_LIBRARY_PATH does not point to incompatible sherpa/onnx runtime libraries.",
                    cause=error,
                )

        model_key = getattr(self.backend_config, "model", None)
        if not model_key:
            raise TJBotError(
                "Sherpa-ONNX STT requires a model key in listen.backend.local.model"
            )

        try:
            from ...utils.model_registry import ModelRegistry

            registry = ModelRegistry.get_instance()
            model_info = registry.load_model(model_key)
            model_dir = registry.get_model_cache_dir_for_type("stt") / model_info.folder
            paths = _model_paths(model_key, model_dir)
            self._model_kind = paths["kind"]

            # Load VAD model if configured and model is offline
            vad_config = getattr(self.backend_config, "vad", None)
            if (
                vad_config
                and self._model_kind
                and self._model_kind.startswith("offline")
            ):
                vad_enabled = getattr(vad_config, "enabled", True)
                vad_model_key = getattr(vad_config, "model", None)
                if vad_enabled and vad_model_key:
                    logger.info(f"Loading VAD model: {vad_model_key}")
                    vad_info = registry.load_model(vad_model_key)
                    vad_cache_dir = registry.get_model_cache_dir_for_type("vad")
                    self._vad_path = str(
                        vad_cache_dir / vad_info.folder / vad_info.required[0]
                    )

            if paths["kind"] == "offline-moonshine":
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_moonshine(
                    preprocessor=paths["preprocessor"],
                    encoder=paths["encoder"],
                    uncached_decoder=paths["uncached_decoder"],
                    cached_decoder=paths["cached_decoder"],
                    tokens=paths["tokens"],
                    num_threads=2,
                    decoding_method="greedy_search",
                    debug=False,
                )

            elif paths["kind"] == "offline-whisper":
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                    encoder=paths["encoder"],
                    decoder=paths["decoder"],
                    tokens=paths["tokens"],
                    language="en",
                    task="transcribe",
                    num_threads=2,
                    decoding_method="greedy_search",
                    debug=False,
                )

            elif paths["kind"] == "streaming-zipformer":
                self.recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                    tokens=paths["tokens"],
                    encoder=paths["encoder"],
                    decoder=paths["decoder"],
                    joiner=paths["joiner"],
                    num_threads=2,
                    sample_rate=16000,
                    feature_dim=80,
                    decoding_method="greedy_search",
                    enable_endpoint_detection=True,
                    rule1_min_trailing_silence=2.4,
                    rule2_min_trailing_silence=1.2,
                    rule3_min_utterance_length=1.2,
                )

            elif paths["kind"] == "streaming-paraformer":
                self.recognizer = sherpa_onnx.OnlineRecognizer.from_paraformer(
                    encoder=paths["encoder"],
                    decoder=paths["decoder"],
                    tokens=paths["tokens"],
                    num_threads=2,
                    sample_rate=16000,
                    feature_dim=80,
                    decoding_method="greedy_search",
                    enable_endpoint_detection=True,
                    rule1_min_trailing_silence=2.4,
                    rule2_min_trailing_silence=1.2,
                    rule3_min_utterance_length=1.2,
                )

            else:
                raise TJBotError(f"Unsupported model kind: {paths['kind']}")

            logger.info(
                f"Sherpa-ONNX STT initialized (model={model_key}, kind={self._model_kind})"
            )

        except TJBotError:
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Sherpa-ONNX STT: {e}")
            raise TJBotError(f"Failed to initialize Sherpa-ONNX STT: {e}")

    def transcribe(
        self, audio_stream: Iterable[bytes], options: Optional[STTRequestOptions] = None
    ) -> str:
        if not self.recognizer:
            raise TJBotError("Sherpa-ONNX STT not initialized.")

        options = options or {}
        abort_signal = options.get("abort_signal")
        on_partial_result = options.get("on_partial_result")
        on_final_result = options.get("on_final_result")

        self.raise_if_aborted(options)

        try:
            if self._model_kind in ("streaming-zipformer", "streaming-paraformer"):
                transcript = self._transcribe_online(
                    audio_stream, on_partial_result, on_final_result, abort_signal
                )
            elif self._should_use_vad():
                transcript = self._transcribe_offline_with_vad(
                    audio_stream, on_partial_result, on_final_result, abort_signal
                )
            else:
                transcript = self._transcribe_offline_energy(
                    audio_stream, on_partial_result, on_final_result, abort_signal
                )

            if not transcript.strip():
                raise TJBotError(
                    "STT: No speech could be recognized", code="stt.no-speech"
                )
            return transcript
        except Exception as e:
            if isinstance(e, TJBotError):
                if e.code != "stt.aborted":
                    logger.error(f"Sherpa STT error: {e}")
                raise
            logger.error(f"Sherpa STT error: {e}")
            raise TJBotError(f"Sherpa STT error: {e}", cause=e)

    def _should_use_vad(self) -> bool:
        """Return True if VAD path is loaded and model kind is offline."""
        if not self._model_kind or not self._model_kind.startswith("offline"):
            return False
        vad_config = getattr(self.backend_config, "vad", None)
        vad_enabled = getattr(vad_config, "enabled", True) if vad_config else True
        return bool(self._vad_path and vad_enabled)

    def _create_silero_vad(self, model_path: str):
        """Create a Silero VAD instance. Mirrors Node createSileroVad()."""
        config = sherpa_onnx.VadModelConfig(
            silero_vad=sherpa_onnx.SileroVadModelConfig(
                model=model_path,
                threshold=0.5,
                min_speech_duration=0.25,
                min_silence_duration=0.5,
                window_size=512,
            ),
            sample_rate=16000,
            num_threads=1,
            debug=False,
        )
        return sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=60)

    @staticmethod
    def _vad_queue_empty(vad: Any) -> bool:
        """Return True when the sherpa VAD segment queue is empty across API variants."""
        empty = getattr(vad, "empty", None)
        if callable(empty):
            return bool(empty())

        is_empty = getattr(vad, "is_empty", None)
        if callable(is_empty):
            return bool(is_empty())

        raise TJBotError("Sherpa VAD object does not expose an empty()/is_empty() API")

    @staticmethod
    def _vad_front(vad: Any) -> Any:
        """Return the next VAD segment across sherpa API variants."""
        front = getattr(vad, "front", None)
        if front is None:
            raise TJBotError("Sherpa VAD object does not expose a front API")
        return front() if callable(front) else front

    @staticmethod
    def _vad_pop(vad: Any) -> None:
        """Advance the VAD queue across sherpa API variants."""
        pop = getattr(vad, "pop", None)
        if pop is None:
            raise TJBotError("Sherpa VAD object does not expose a pop API")
        if callable(pop):
            pop()

    def _transcribe_offline_with_vad(
        self,
        audio_stream: Iterable[bytes],
        on_partial_result: Optional[Callable[[str], None]],
        on_final_result: Optional[Callable[[str], None]],
        abort_signal: Optional[object] = None,
    ) -> str:
        """Decode each VAD-segmented speech chunk with the offline recognizer."""
        recognizer = self.recognizer
        vad = self._create_silero_vad(self._vad_path or "")
        sample_rate = 16000

        for chunk in audio_stream:
            if self._is_abort_signal_set(abort_signal):
                raise TJBotError("STT transcription was aborted.", code="stt.aborted")
            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            vad.accept_waveform(samples)

            while not self._vad_queue_empty(vad):
                segment = self._vad_front(vad)
                self._vad_pop(vad)

                stream = recognizer.create_stream()
                stream.accept_waveform(sample_rate, segment.samples)
                recognizer.decode_stream(stream)

                text = stream.result.text.strip().lower()
                if text:
                    if on_partial_result:
                        on_partial_result(text)
                    if on_final_result:
                        on_final_result(text)
                    return text

        if self._is_abort_signal_set(abort_signal):
            raise TJBotError("STT transcription was aborted.", code="stt.aborted")
        return ""

    def _transcribe_offline_energy(
        self,
        audio_stream: Iterable[bytes],
        on_partial_result: Optional[Callable[[str], None]],
        on_final_result: Optional[Callable[[str], None]],
        abort_signal: Optional[object] = None,
    ) -> str:
        """Energy-based silence detection for offline models (fallback when no VAD)."""
        recognizer = self.recognizer
        sample_rate = 16000
        speech_chunks: list = []
        silence_ms = 0.0
        silence_limit_ms = 700.0
        rms_threshold = 1e-4

        for chunk in audio_stream:
            if self._is_abort_signal_set(abort_signal):
                raise TJBotError("STT transcription was aborted.", code="stt.aborted")
            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0
            duration_ms = (len(samples) / sample_rate) * 1000.0

            if rms > rms_threshold:
                speech_chunks.append(samples)
                silence_ms = 0.0
            else:
                silence_ms += duration_ms

            if speech_chunks and silence_ms >= silence_limit_ms:
                combined = np.concatenate(speech_chunks)
                stream = recognizer.create_stream()
                stream.accept_waveform(sample_rate, combined)
                recognizer.decode_stream(stream)

                text = stream.result.text.strip().lower()
                if text:
                    if on_partial_result:
                        on_partial_result(text)
                    if on_final_result:
                        on_final_result(text)
                    return text

                speech_chunks.clear()
                silence_ms = 0.0

        if self._is_abort_signal_set(abort_signal):
            raise TJBotError("STT transcription was aborted.", code="stt.aborted")

        # Stream ended — decode whatever is left
        if speech_chunks:
            combined = np.concatenate(speech_chunks)
            stream = recognizer.create_stream()
            stream.accept_waveform(sample_rate, combined)
            recognizer.decode_stream(stream)
            text = stream.result.text.strip().lower()
            if text:
                if on_final_result:
                    on_final_result(text)
                return text

        if self._is_abort_signal_set(abort_signal):
            raise TJBotError("STT transcription was aborted.", code="stt.aborted")
        return ""

    def _transcribe_online(
        self,
        audio_stream: Iterable[bytes],
        on_partial_result: Optional[Callable[[str], None]],
        on_final_result: Optional[Callable[[str], None]],
        abort_signal: Optional[object] = None,
    ) -> str:
        """Stream audio into an online recognizer (zipformer / paraformer)."""
        recognizer = self.recognizer
        stream = recognizer.create_stream()
        last_text = ""
        final_text = ""

        for chunk in audio_stream:
            if self._is_abort_signal_set(abort_signal):
                raise TJBotError("STT transcription was aborted.", code="stt.aborted")
            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            stream.accept_waveform(16000, samples)

            while recognizer.is_ready(stream):
                recognizer.decode_stream(stream)

            text = recognizer.get_result(stream).text.strip().lower()
            is_endpoint = recognizer.is_endpoint(stream)

            if text and text != last_text:
                last_text = text
                if on_partial_result:
                    on_partial_result(text)

            if is_endpoint:
                tail = np.zeros(int(16000 * 1.5), dtype=np.float32)
                stream.accept_waveform(16000, tail)
                while recognizer.is_ready(stream):
                    recognizer.decode_stream(stream)
                text = recognizer.get_result(stream).text.strip().lower()
                if text:
                    final_text = text
                    if on_final_result:
                        on_final_result(text)
                recognizer.reset(stream)
                return final_text

        if self._is_abort_signal_set(abort_signal):
            raise TJBotError("STT transcription was aborted.", code="stt.aborted")

        stream.input_finished()
        while recognizer.is_ready(stream):
            recognizer.decode_stream(stream)
        text = recognizer.get_result(stream).text.strip().lower()
        if text:
            final_text = text
            if on_final_result:
                on_final_result(text)
        if self._is_abort_signal_set(abort_signal):
            raise TJBotError("STT transcription was aborted.", code="stt.aborted")
        return final_text
