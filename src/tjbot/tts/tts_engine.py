from abc import ABC, abstractmethod
from ..config.config_types import SpeakConfig, TTSBackendConfig, TTSEngineConfig
from ..utils.errors import TJBotError


class TTSEngine(ABC):
	"""Abstract base class for TTS engines."""

	def __init__(self, config: TTSEngineConfig):
		self.config = config

	@abstractmethod
	async def initialize(self) -> None:
		"""Initialize the TTS engine. Must be called before synthesize()."""
		pass

	async def cleanup(self) -> None:
		"""Release any resources held by this engine."""
		return

	@abstractmethod
	async def synthesize(self, text: str) -> bytes:
		"""Synthesize text to WAV/PCM bytes."""
		pass

	def validate_text(self, text: str) -> None:
		if not text or not isinstance(text, str) or not text.strip():
			raise TJBotError('Text input cannot be empty or whitespace-only')


async def create_tts_engine(speak_config: SpeakConfig) -> TTSEngine:
	backend_config: TTSBackendConfig = speak_config.backend or TTSBackendConfig()
	backend_type = backend_config.type or 'local'

	if backend_type == 'none':
		class NoneTTSEngine(TTSEngine):
			async def initialize(self) -> None:
				return

			async def synthesize(self, text: str) -> bytes:
				_ = text
				raise TJBotError(
					'TTS is disabled. Configure a text-to-speech backend (local, ibm-watson-tts, google-cloud-tts, or azure-tts) to use speech synthesis.'
				)

		return NoneTTSEngine({})

	if backend_type == 'ibm-watson-tts':
		from .backends.ibm_watson_tts import IBMWatsonTTSEngine

		return IBMWatsonTTSEngine(backend_config.ibm_watson_tts)

	if backend_type == 'google-cloud-tts':
		from .backends.google_cloud_tts import GoogleCloudTTSEngine

		return GoogleCloudTTSEngine(backend_config.google_cloud_tts)

	if backend_type == 'azure-tts':
		from .backends.azure_tts import AzureTTSEngine

		return AzureTTSEngine(backend_config.azure_tts)

	if backend_type == 'local':
		from .backends.sherpa_onnx_tts import SherpaONNXTTSEngine

		return SherpaONNXTTSEngine(backend_config.local)

	raise TJBotError(f'Unknown TTS backend type: {backend_type}')

__all__ = ["TTSEngine", "create_tts_engine"]
