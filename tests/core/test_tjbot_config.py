import asyncio
import pytest
from tjbot.config import TJBotConfig
from tjbot.config.config_types import HardwareConfig
from tjbot.utils.errors import TJBotError
from tjbot.stt.stt import STTController
from tjbot.tts.tts import TTSController
from tjbot.vision.vision_engine import create_vision_engine

def test_default_config_loading(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path / 'home-empty'))
    config = TJBotConfig()
    assert config.log.level == 'info'
    assert config.hardware is not None
    assert config.hardware.led is False
    # Check that listen config exists and has reasonable defaults
    assert config.listen is not None
    assert config.listen.microphone_rate > 0

def test_override_config(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path / 'home-empty'))
    overrides = {
        'log': {'level': 'debug'},
        'hardware': {'camera': True}
    }
    config = TJBotConfig(overrides)
    assert config.log.level == 'debug'
    assert config.hardware.camera is True
    assert config.hardware.servo is False # Default is false usually in test override context? Need to check default.toml

def test_nested_override():
    overrides = {
        'shine': {
            'neopixel': {
                'gpioPin': 10
            }
        }
    }
    config = TJBotConfig(overrides)
    # Check only changed value, others should remain default
    assert config.shine.neopixel is not None
    assert config.shine.neopixel.gpio_pin == 10


def test_node_style_led_config_fields_parse():
    config = TJBotConfig(
        {
            'hardware': {'led': True},
            'shine': {
                'hasNeopixelLED': True,
                'neopixel': {'gpioPin': 10},
            },
        }
    )

    assert config.hardware.led is True
    assert config.shine.has_neopixel_led is True


def test_backend_type_none_is_valid_for_stt_tts():
    overrides = {
        'listen': {
            'backend': {
                'type': 'none',
            }
        },
        'speak': {
            'backend': {
                'type': 'none',
            }
        }
    }

    config = TJBotConfig(overrides)
    assert config.listen.backend is not None
    assert config.listen.backend.type == 'none'
    assert config.speak.backend is not None
    assert config.speak.backend.type == 'none'


def test_google_and_azure_backend_extra_fields_parse():
    overrides = {
        'listen': {
            'backend': {
                'type': 'google-cloud-stt',
                'google-cloud-stt': {
                    'languageCode': 'en-US',
                    'region': 'us-central1',
                    'profanityFilter': True,
                    'credentialsPath': '/tmp/gcp.json',
                }
            }
        },
        'speak': {
            'backend': {
                'type': 'azure-tts',
                'azure-tts': {
                    'voiceName': 'en-US-JennyNeural',
                    'region': 'eastus',
                    'key': 'dummy',
                }
            }
        }
    }

    config = TJBotConfig(overrides)

    assert config.listen.backend is not None
    assert config.listen.backend.google_cloud_stt is not None
    assert config.listen.backend.google_cloud_stt.region == 'us-central1'
    assert config.listen.backend.google_cloud_stt.profanityFilter is True

    assert config.speak.backend is not None
    assert config.speak.backend.azure_tts is not None
    assert config.speak.backend.azure_tts.voiceName == 'en-US-JennyNeural'
    assert config.speak.backend.azure_tts.region == 'eastus'


def test_stt_none_backend_raises_descriptive_error():
    config = TJBotConfig({'listen': {'backend': {'type': 'none'}}})
    controller = STTController(config.listen)

    with pytest.raises(TJBotError, match='STT is disabled'):
        controller.transcribe(iter([b'abc']))


def test_tts_none_backend_raises_descriptive_error():
    class DummySpeaker:
        def play_audio(self, file_path):
            _ = file_path

    config = TJBotConfig({'speak': {'backend': {'type': 'none'}}})
    controller = TTSController(DummySpeaker())
    controller.initialize(config.speak)

    with pytest.raises(TJBotError, match='TTS is disabled'):
        controller.speak('hello')


def test_vision_backend_type_none_and_google_parse():
    config = TJBotConfig(
        {
            'see': {
                'backend': {
                    'type': 'google-cloud-vision',
                    'google-cloud-vision': {
                        'credentialsPath': '/tmp/google-vision.json',
                        'objectDetectionConfidence': 0.6,
                    },
                }
            }
        }
    )

    assert config.see.backend is not None
    assert config.see.backend.type == 'google-cloud-vision'
    assert config.see.backend.google_cloud_vision is not None
    assert config.see.backend.google_cloud_vision.credentials_path == '/tmp/google-vision.json'


def test_vision_none_backend_raises_descriptive_error():
    config = TJBotConfig({'see': {'backend': {'type': 'none'}}})
    engine = asyncio.run(create_vision_engine(config.see))

    with pytest.raises(TJBotError, match='Vision is disabled'):
        asyncio.run(engine.detect_objects(b'image'))


def test_google_cloud_vision_confidence_thresholds_accept_valid_range():
    config = TJBotConfig(
        {
            'see': {
                'backend': {
                    'type': 'google-cloud-vision',
                    'google-cloud-vision': {
                        'objectDetectionConfidence': 0.7,
                        'imageClassificationConfidence': 0.6,
                        'faceDetectionConfidence': 0.5,
                    },
                }
            }
        }
    )

    assert config.see.backend is not None
    assert config.see.backend.google_cloud_vision is not None
    assert config.see.backend.google_cloud_vision.object_detection_confidence == 0.7
    assert config.see.backend.google_cloud_vision.image_classification_confidence == 0.6
    assert config.see.backend.google_cloud_vision.face_detection_confidence == 0.5


def test_azure_vision_confidence_thresholds_accept_valid_range():
    config = TJBotConfig(
        {
            'see': {
                'backend': {
                    'type': 'azure-vision',
                    'azure-vision': {
                        'objectDetectionConfidence': 0.7,
                        'imageClassificationConfidence': 0.6,
                    },
                }
            }
        }
    )

    assert config.see.backend is not None
    assert config.see.backend.azure_vision is not None
    assert config.see.backend.azure_vision.object_detection_confidence == 0.7
    assert config.see.backend.azure_vision.image_classification_confidence == 0.6


def test_google_cloud_vision_confidence_thresholds_reject_out_of_range():
    with pytest.raises(TJBotError, match='invalid TJBot configuration'):
        TJBotConfig(
            {
                'see': {
                    'backend': {
                        'type': 'google-cloud-vision',
                        'google-cloud-vision': {
                            'objectDetectionConfidence': 1.5,
                        },
                    }
                }
            }
        )


def test_config_schema_rejects_invalid_log_level():
    with pytest.raises(TJBotError, match='invalid TJBot configuration'):
        TJBotConfig({'log': {'level': 'super-loud'}})
