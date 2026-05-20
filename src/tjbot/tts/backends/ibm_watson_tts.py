import logging
from typing import Optional

from ..tts_engine import TTSEngine
from ...config.config_types import TTSBackendIBMWatsonConfig
from ...utils.errors import TJBotError
from ...utils.credentials import load_ibm_watson_cloud_credentials

try:
	from ibm_watson import TextToSpeechV1
	from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
except ImportError:
	TextToSpeechV1 = None
	IAMAuthenticator = None

logger = logging.getLogger(__name__)


class IBMWatsonTTSEngine(TTSEngine):
	"""
	IBM Watson Text-to-Speech backend.
	"""

	def __init__(self, config: Optional[TTSBackendIBMWatsonConfig] = None):
		super().__init__(config.model_dump(by_alias=True) if config else {})
		self.backend_config = config
		self.service = None

	async def initialize(self) -> None:
		if TextToSpeechV1 is None:
			raise TJBotError('ibm-watson library not installed. Please install it.')

		voice = self.backend_config.voice if self.backend_config else None
		if not voice:
			raise TJBotError(
				'IBM Watson TTS voice not specified. Provide voice in speak.backend.ibm-watson-tts config.'
			)

		credentials_path = getattr(self.backend_config, 'credentials_path', None) or ''
		load_ibm_watson_cloud_credentials(credentials_path)

		try:
			apikey = getattr(self.backend_config, 'apikey', None)
			url = getattr(self.backend_config, 'url', None)

			if apikey:
				authenticator = IAMAuthenticator(apikey)
				self.service = TextToSpeechV1(authenticator=authenticator)
				if url:
					self.service.set_service_url(url)
			else:
				self.service = TextToSpeechV1(authenticator=None)

			logger.info('Watson TTS initialized')
		except Exception as e:
			logger.error('Failed to initialize Watson TTS: %s', e)
			raise TJBotError(f'Failed to initialize Watson TTS: {e}')

	async def synthesize(self, text: str) -> bytes:
		if not self.service:
			raise TJBotError('IBM Watson TTS service not initialized. Call initialize() first.')

		self.validate_text(text)

		voice = self.backend_config.voice if self.backend_config else None
		if not voice:
			raise TJBotError('IBM Watson TTS voice not specified. Provide voice in speak config.')

		try:
			response = self.service.synthesize(
				text,
				voice=voice,
				accept='audio/wav'
			).get_result()
			return response.content
		except Exception as e:
			logger.error('Watson TTS synthesis error: %s', e)
			raise TJBotError('IBM Watson TTS synthesis failed', cause=e)


__all__ = ["IBMWatsonTTSEngine"]
