import logging
from typing import Optional
from ..engine import TTSEngine
from ...config.models import SherpaOnnxTTSConfig
from ...error import TJBotError

try:
    import sherpa_onnx
except ImportError:
    sherpa_onnx = None

logger = logging.getLogger(__name__)

class SherpaONNXTTSEngine(TTSEngine):
    """
    Sherpa-ONNX (Local) Text-to-Speech backend.
    """
    def __init__(self, config: Optional[SherpaOnnxTTSConfig] = None):
        self.backend_config = config
        self.synthesizer = None
        self._initialize()

    def _initialize(self):
        if sherpa_onnx is None:
             raise TJBotError("sherpa-onnx library not installed. Please install it.")

        try:
            model = self.backend_config.model
            tokens = self.backend_config.tokens
            data_dir = self.backend_config.dataDir

            if not model or not tokens:
                 raise TJBotError("Sherpa-ONNX TTS requires model and tokens paths.")

            # Sherpa TTS config
            # Vits model config
            vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=model,
                lexicon="",
                tokens=tokens,
                data_dir=data_dir if data_dir else "",
            )
            model_config = sherpa_onnx.OfflineTtsModelConfig(vits=vits_config)

            config = sherpa_onnx.OfflineTtsConfig(
                model=model_config,
                rule_fsts="",
                max_num_sentences=1,
            )

            self.synthesizer = sherpa_onnx.OfflineTts(config)
            logger.info("Sherpa-ONNX TTS initialized")

        except Exception as e:
             # Try Matcha/Kokoro if VITS fails? Node implementation checks types (vits, matcha, etc)
             # Node impl logic is complex, handling multiple model types.
             # For this port, we start with VITS as default fallback or generic.
             logger.error(f"Failed to initialize Sherpa-ONNX TTS: {e}")

    def synthesize(self, text: str) -> bytes:
        if not self.synthesizer:
             raise TJBotError("Sherpa-ONNX TTS not initialized.")

        try:
            # generate() returns audio object with samples (float array) and sample_rate
            audio = self.synthesizer.generate(text, sid=0, speed=1.0)

            if not audio or len(audio.samples) == 0:
                 raise TJBotError("Sherpa TTS produced no audio.")

            # Convert float32 samples to int16 bytes for playback (aplay usually likes int16 wav)
            # Or assume speaker controller handles it.
            # Speaker controller in `speaker.py` uses `aplay file`.
            # So we return WAV bytes.

            import wave
            import io
            import numpy as np

            # Convert float samples [-1, 1] to int16
            samples = np.array(audio.samples)
            samples_int16 = (samples * 32767).astype(np.int16)

            with io.BytesIO() as wav_buffer:
                with wave.open(wav_buffer, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2) # 16 bit
                    wav_file.setframerate(audio.sample_rate)
                    wav_file.writeframes(samples_int16.tobytes())

                return wav_buffer.getvalue()

        except Exception as e:
            logger.error(f"Sherpa TTS synthesis error: {e}")
            raise TJBotError(f"Sherpa TTS error: {e}")
