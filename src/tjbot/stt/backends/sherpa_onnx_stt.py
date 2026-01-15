from typing import Iterator, Callable, Optional, Dict, Any
import logging
from ..engine import STTEngine
from ...error import TJBotError

try:
    import sherpa_onnx
except ImportError:
    sherpa_onnx = None

logger = logging.getLogger(__name__)

class SherpaONNXSTTEngine(STTEngine):
    """
    Sherpa-ONNX (Local) Speech-to-Text backend.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.backend_config = config
        self.recognizer = None
        self._initialize()

    def _initialize(self):
        if sherpa_onnx is None:
             raise TJBotError("sherpa-onnx library not installed. Please install it.")

        # Sherpa-ONNX needs model paths
        # model (encoder, decoder, joiner for transducer OR tokens+encoder+decoder for others)

        # Config structure in models.py:
        # tokens: str
        # encoder: str
        # decoder: str
        # joiner: str
        # type: str (transducer, zipformer, etc? Node impl handles different types)

        # We need to construct sherpa_onnx.OnlineRecognizerConfig

        try:
            tokens = self.backend_config.tokens
            encoder = self.backend_config.encoder
            decoder = self.backend_config.decoder
            joiner = self.backend_config.joiner

            if not tokens or not encoder or not decoder or not joiner:
                 raise TJBotError("Sherpa-ONNX STT requires paths to: tokens, encoder, decoder, joiner. Please set them in config.")

            recognizer_config = sherpa_onnx.OnlineRecognizerConfig(
                tokens=tokens,
                transducer=sherpa_onnx.OnlineTransducerModelConfig(
                    encoder=encoder,
                    decoder=decoder,
                    joiner=joiner
                ),
            )

            self.recognizer = sherpa_onnx.OnlineRecognizer(recognizer_config)
            logger.info("Sherpa-ONNX STT initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Sherpa-ONNX STT: {e}")

    def transcribe(
        self,
        audio_stream: Iterator[bytes],
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ) -> str:
        if not self.recognizer:
             raise TJBotError("Sherpa-ONNX STT not initialized.")

        stream = self.recognizer.create_stream()

        # final_transcript_acc = ""

        try:
            for chunk in audio_stream:
                # Sherpa expects float array usually? Or valid bytes?
                # The python binding `stream.accept_waveform(sample_rate, samples)` usually takes float samples.
                # If we get raw bytes (int16), we need to decode.

                import numpy as np
                # Assume int16
                samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0

                stream.accept_waveform(16000, samples) # Assume 16k

                while self.recognizer.is_ready(stream):
                    self.recognizer.decode_stream(stream)

                result = self.recognizer.get_result(stream)
                text = result.text

                # Logic to detect partial/final?
                # Sherpa online recognizer usually gives cumulative text.
                if text:
                    if on_partial_result:
                        on_partial_result(text)

            # End of stream
            stream.input_finished()
            while self.recognizer.is_ready(stream):
                self.recognizer.decode_stream(stream)

            final_transcript = self.recognizer.get_result(stream).text
            if on_final_result:
                on_final_result(final_transcript)

            return final_transcript

        except Exception as e:
            logger.error(f"Sherpa STT error: {e}")
            if on_error:
                on_error(e)
            raise TJBotError(f"Sherpa STT error: {e}")
