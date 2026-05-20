"""
Tests for stt_utils.py - infer_stt_mode and infer_local_model_flavor
"""
import pytest
from tjbot.stt.stt_utils import infer_stt_mode, infer_local_model_flavor, to_model_type
from tjbot.config.config_types import ListenConfig, STTBackendConfig, STTBackendLocalConfig, STTBackendIBMWatsonConfig, STTBackendGoogleCloudConfig, STTBackendAzureConfig
from tjbot.utils.errors import TJBotError


class TestInferLocalModelFlavor:
    def test_whisper(self):
        assert infer_local_model_flavor('whisper-tiny') == 'offline-whisper'

    def test_moonshine(self):
        assert infer_local_model_flavor('moonshine-base') == 'offline-moonshine'

    def test_zipformer(self):
        assert infer_local_model_flavor('streaming-zipformer-en') == 'streaming-zipformer'

    def test_transducer(self):
        assert infer_local_model_flavor('transducer-model') == 'streaming-zipformer'

    def test_paraformer(self):
        assert infer_local_model_flavor('paraformer-en-streaming') == 'streaming-paraformer'

    def test_url_fallback(self):
        assert infer_local_model_flavor(None, 'https://huggingface.co/models/whisper-large') == 'offline-whisper'

    def test_unknown_raises(self):
        with pytest.raises(TJBotError, match='Unable to infer STT model type'):
            infer_local_model_flavor('unknown-model')


class TestToModelType:
    def test_streaming_flavors(self):
        assert to_model_type('streaming-zipformer') == 'streaming'
        assert to_model_type('streaming-paraformer') == 'streaming'

    def test_offline_flavors(self):
        assert to_model_type('offline-whisper') == 'offline'
        assert to_model_type('offline-moonshine') == 'offline'


class TestInferSTTMode:
    def _config(self, backend_type, **kwargs):
        backend = STTBackendConfig(type=backend_type)
        return ListenConfig(backend=backend)

    def test_ibm_watson_no_interim(self):
        cfg = ListenConfig(backend=STTBackendConfig(
            type='ibm-watson-stt',
            **{'ibm-watson-stt': STTBackendIBMWatsonConfig(interim_results=False)}
        ))
        assert infer_stt_mode(cfg) == 'offline'

    def test_ibm_watson_interim(self):
        cfg = ListenConfig(backend=STTBackendConfig(
            type='ibm-watson-stt',
            **{'ibm-watson-stt': STTBackendIBMWatsonConfig(interim_results=True)}
        ))
        assert infer_stt_mode(cfg) == 'streaming'

    def test_google_cloud_no_interim(self):
        cfg = ListenConfig(backend=STTBackendConfig(
            type='google-cloud-stt',
            **{'google-cloud-stt': STTBackendGoogleCloudConfig(interim_results=False)}
        ))
        assert infer_stt_mode(cfg) == 'offline'

    def test_google_cloud_interim(self):
        cfg = ListenConfig(backend=STTBackendConfig(
            type='google-cloud-stt',
            **{'google-cloud-stt': STTBackendGoogleCloudConfig(interim_results=True)}
        ))
        assert infer_stt_mode(cfg) == 'streaming'

    def test_azure_always_offline(self):
        cfg = ListenConfig(backend=STTBackendConfig(type='azure-stt'))
        assert infer_stt_mode(cfg) == 'offline'

    def test_none_backend_offline(self):
        cfg = ListenConfig(backend=STTBackendConfig(type='none'))
        assert infer_stt_mode(cfg) == 'offline'

    def test_local_whisper_offline(self):
        cfg = ListenConfig(backend=STTBackendConfig(
            type='local',
            local=STTBackendLocalConfig(model='whisper-tiny')
        ))
        assert infer_stt_mode(cfg) == 'offline'

    def test_local_zipformer_streaming(self):
        cfg = ListenConfig(backend=STTBackendConfig(
            type='local',
            local=STTBackendLocalConfig(model='streaming-zipformer-en')
        ))
        assert infer_stt_mode(cfg) == 'streaming'

    def test_unknown_backend_raises(self):
        backend = STTBackendConfig.model_construct(type='unknown-backend')
        cfg = ListenConfig.model_construct(backend=backend)
        with pytest.raises(TJBotError, match='Unknown STT backend type'):
            infer_stt_mode(cfg)
