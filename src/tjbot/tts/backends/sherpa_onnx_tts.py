import io
import logging
import os
import wave
from pathlib import Path
from typing import Optional

import numpy as np

from ..tts_engine import TTSEngine
from ...config.config_types import TTSBackendLocalConfig
from ...utils.errors import TJBotError
from ...utils.sherpa_runtime import load_sherpa_onnx_module

sherpa_onnx = None

logger = logging.getLogger(__name__)


def _tts_model_paths(key: str, model_dir: Path) -> dict:
    """Return file paths for a given TTS model key."""
    if key.startswith('vits-piper'):
        # The .onnx file name matches the last two segments of the key joined by hyphen,
        # e.g. vits-piper-en_US-ryan-medium → en_US-ryan-medium.onnx
        # The folder name already encodes this; find the .onnx file directly.
        onnx_files = list(model_dir.glob('*.onnx'))
        if not onnx_files:
            raise TJBotError(f"No .onnx file found in {model_dir}")
        model_file = str(onnx_files[0])
        tokens_file = str(model_dir / 'tokens.txt')
        espeak_data = model_dir / 'espeak-ng-data'
        data_dir = str(espeak_data) if espeak_data.exists() else str(model_dir)
        return {
            'kind': 'vits',
            'model': model_file,
            'tokens': tokens_file,
            'data_dir': data_dir,
        }
    raise TJBotError(f"Unsupported TTS model key: {key}")


class SherpaONNXTTSEngine(TTSEngine):
    """Sherpa-ONNX (Local) Text-to-Speech backend."""

    def __init__(self, config: Optional[TTSBackendLocalConfig] = None):
        super().__init__(config.model_dump(by_alias=True) if config else {})
        self.backend_config = config
        self.synthesizer = None

    async def initialize(self) -> None:
        global sherpa_onnx

        if not os.environ.get('SHERPA_ONNX_LOG_LEVEL'):
            os.environ['SHERPA_ONNX_LOG_LEVEL'] = 'OFF'

        if sherpa_onnx is None:
            try:
                sherpa_onnx = load_sherpa_onnx_module()
            except Exception as error:
                raise TJBotError(
                    'sherpa-onnx library is unavailable. Ensure the package is installed and '
                    'LD_LIBRARY_PATH does not point to incompatible sherpa/onnx runtime libraries.',
                    cause=error,
                )

        model_key = getattr(self.backend_config, 'model', None)
        if not model_key:
            raise TJBotError(
                'Sherpa-ONNX TTS model not specified. Provide model name in speak.backend.sherpa-onnx config.'
            )

        try:
            from ...utils.model_registry import ModelRegistry
            registry = ModelRegistry.get_instance()
            model_info = registry.load_model(model_key)
            model_dir = registry.get_model_cache_dir_for_type('tts') / model_info.folder
            paths = _tts_model_paths(model_key, model_dir)

            if paths['kind'] == 'vits':
                try:
                    vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=paths['model'],
                        lexicon='',
                        tokens=paths['tokens'],
                        data_dir=paths['data_dir'],
                        noise_scale=0.667,
                        noise_scale_w=0.8,
                        length_scale=1.0,
                    )
                    model_config = sherpa_onnx.OfflineTtsModelConfig(
                        vits=vits_config,
                        num_threads=1,
                        provider='cpu',
                        debug=False,
                    )
                except TypeError:
                    # Older bindings may not expose all tuning/provider fields.
                    vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=paths['model'],
                        lexicon='',
                        tokens=paths['tokens'],
                        data_dir=paths['data_dir'],
                    )
                    model_config = sherpa_onnx.OfflineTtsModelConfig(vits=vits_config)

                tts_config = sherpa_onnx.OfflineTtsConfig(model=model_config, rule_fsts='', max_num_sentences=1)
                self.synthesizer = sherpa_onnx.OfflineTts(tts_config)
            else:
                raise TJBotError(f"Unsupported TTS model kind: {paths['kind']}")

            logger.info(f"Sherpa-ONNX TTS initialized (model={model_key})")

        except TJBotError:
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Sherpa-ONNX TTS: {e}")
            raise TJBotError(f"Failed to initialize Sherpa-ONNX TTS: {e}")

    async def synthesize(self, text: str) -> bytes:
        if not self.synthesizer:
            raise TJBotError('TTS engine not initialized. Call initialize() first.')

        self.validate_text(text)

        try:
            # generate() returns audio object with samples (float array) and sample_rate
            audio = self.synthesizer.generate(text, sid=0, speed=1.0)

            if not audio or len(audio.samples) == 0:
                raise TJBotError('Sherpa TTS produced no audio.')

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
