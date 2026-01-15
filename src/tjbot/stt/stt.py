import logging
from typing import Iterator, Callable, Optional
from ..config.models import ListenConfig
from ..error import TJBotError
from .engine import STTEngine

logger = logging.getLogger(__name__)

# Import backends appropriately (lazy load or factory)
# from .backends.local import LocalSTT
# from .backends.watson import WatsonSTT
# ...

class STTController:
    """
    STT Controller that manages the active STT engine.
    """
    def __init__(self, listen_config: ListenConfig):
        self.config = listen_config
        self.engine: Optional[STTEngine] = None
        self._initialize_engine()

    def _initialize_engine(self):
        # backend_config: STTBackendConfig = self.config.backend or STTBackendConfig()
        # backend_type = backend_config.type

        # Select engine based on type
        # For now, we stub this factory logic.
        # In a real impl, we would instantiate the correct engine class.

        # Example stub:
        # if backend_type == 'local':
        #     self.engine = LocalSTT(backend_config.local)
        # elif backend_type == 'ibm-watson-stt':
        #     self.engine = WatsonSTT(backend_config.ibm_watson_stt)
        # ...

        # For the purpose of this porting plan, we'll assume we need to implement at least one.
        pass

    def transcribe(
        self,
        audio_stream: Iterator[bytes],
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None
    ) -> str:
        if not self.engine:
             raise TJBotError("STT engine not initialized.")

        return self.engine.transcribe(
            audio_stream,
            on_partial_result=on_partial_result,
            on_final_result=on_final_result
        )
