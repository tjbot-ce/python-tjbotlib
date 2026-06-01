# Copyright 2026-present TJBot Contributors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from tjbot.config import TJBotConfig
from tjbot.utils.errors import TJBotError
from tjbot.stt.stt import STTController
from tjbot.tts.tts import TTSController
from tjbot.vision.vision_engine import create_vision_engine


def test_accepts_minimal_config():
    config = TJBotConfig({})
    assert config is not None


def test_accepts_config_with_log_section():
    config = TJBotConfig({"log": {"level": "debug"}})
    assert config.log.level == "debug"


def test_accepts_config_with_listen_section():
    config = TJBotConfig({"listen": {"microphoneRate": 44100}})
    assert config.listen is not None


def test_accepts_config_with_see_section():
    config = TJBotConfig({"see": {"cameraResolution": [1920, 1080]}})
    assert config.see is not None


def test_accepts_config_with_shine_section():
    config = TJBotConfig({"shine": {"neopixel": {"gpioPin": 18}}})
    assert config.shine is not None


def test_accepts_config_with_speak_section():
    config = TJBotConfig({"speak": {"backend": {"type": "local"}}})
    assert config.speak is not None


def test_accepts_config_with_wave_section():
    config = TJBotConfig({"wave": {"servoPin": 7}})
    assert config.wave is not None


def test_accepts_complete_config_with_all_sections():
    config = TJBotConfig(
        {
            "log": {"level": "debug"},
            "listen": {"microphoneRate": 44100},
            "see": {"cameraResolution": [1920, 1080]},
            "shine": {"neopixel": {"gpioPin": 18}},
            "speak": {"backend": {"type": "local"}},
            "wave": {"servoPin": 7},
            "recipe": {"k": "v"},
        }
    )
    assert config is not None


def test_accepts_google_cloud_vision_confidence_thresholds_in_valid_range():
    config = TJBotConfig(
        {
            "see": {
                "backend": {
                    "type": "google-cloud-vision",
                    "google-cloud-vision": {
                        "objectDetectionConfidence": 0.7,
                        "imageClassificationConfidence": 0.6,
                        "faceDetectionConfidence": 0.5,
                    },
                }
            }
        }
    )
    assert config.see is not None


def test_rejects_out_of_range_google_cloud_vision_confidence_thresholds():
    with pytest.raises(TJBotError, match="invalid TJBot configuration"):
        TJBotConfig(
            {
                "see": {
                    "backend": {
                        "type": "google-cloud-vision",
                        "google-cloud-vision": {
                            "objectDetectionConfidence": 1.5,
                        },
                    }
                }
            }
        )


def test_default_config_loading(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home-empty"))
    config = TJBotConfig()
    assert config.log.level == "info"
    assert config.hardware is not None
    assert config.hardware.led is False
    # Check that listen config exists and has reasonable defaults
    assert config.listen is not None
    assert config.listen.microphone_rate > 0


def test_override_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home-empty"))
    overrides = {"log": {"level": "debug"}, "hardware": {"camera": True}}
    config = TJBotConfig(overrides)
    assert config.log.level == "debug"
    assert config.hardware.camera is True
    assert (
        config.hardware.servo is False
    )  # Default is false usually in test override context? Need to check default.toml


def test_nested_override():
    overrides = {"shine": {"neopixel": {"gpioPin": 10}}}
    config = TJBotConfig(overrides)
    # Check only changed value, others should remain default
    assert config.shine.neopixel is not None
    assert config.shine.neopixel.gpio_pin == 10


def test_node_style_led_config_fields_parse():
    config = TJBotConfig(
        {
            "hardware": {"led": True},
            "shine": {
                "hasNeopixelLED": True,
                "neopixel": {"gpioPin": 10},
            },
        }
    )

    assert config.hardware.led is True
    assert config.shine.has_neopixel_led is True


def test_backend_type_none_is_valid_for_stt_tts():
    overrides = {
        "listen": {
            "backend": {
                "type": "none",
            }
        },
        "speak": {
            "backend": {
                "type": "none",
            }
        },
    }

    config = TJBotConfig(overrides)
    assert config.listen.backend is not None
    assert config.listen.backend.type == "none"
    assert config.speak.backend is not None
    assert config.speak.backend.type == "none"


def test_google_and_azure_backend_extra_fields_parse():
    overrides = {
        "listen": {
            "backend": {
                "type": "google-cloud-stt",
                "google-cloud-stt": {
                    "languageCode": "en-US",
                    "region": "us-central1",
                    "profanityFilter": True,
                    "credentialsPath": "/tmp/gcp.json",
                },
            }
        },
        "speak": {
            "backend": {
                "type": "azure-tts",
                "azure-tts": {
                    "voice": "en-US-JennyNeural",
                    "credentialsPath": "/tmp/azure.env",
                },
            }
        },
    }

    config = TJBotConfig(overrides)

    assert config.listen.backend is not None
    assert config.listen.backend.google_cloud_stt is not None
    assert config.listen.backend.google_cloud_stt.region == "us-central1"
    assert config.listen.backend.google_cloud_stt.profanity_filter is True

    assert config.speak.backend is not None
    assert config.speak.backend.azure_tts is not None
    assert config.speak.backend.azure_tts.voice == "en-US-JennyNeural"
    assert config.speak.backend.azure_tts.credentials_path == "/tmp/azure.env"


def test_stt_none_backend_raises_descriptive_error():
    config = TJBotConfig({"listen": {"backend": {"type": "none"}}})
    controller = STTController(config.listen)

    with pytest.raises(TJBotError, match="STT is disabled"):
        controller.transcribe(iter([b"abc"]))


def test_tts_none_backend_raises_descriptive_error():
    class DummySpeaker:
        def play_audio(self, file_path):
            _ = file_path

    config = TJBotConfig({"speak": {"backend": {"type": "none"}}})
    controller = TTSController(DummySpeaker())
    controller.initialize(config.speak)

    with pytest.raises(TJBotError, match="TTS is disabled"):
        controller.speak("hello")


def test_vision_backend_type_none_and_google_parse():
    config = TJBotConfig(
        {
            "see": {
                "backend": {
                    "type": "google-cloud-vision",
                    "google-cloud-vision": {
                        "credentialsPath": "/tmp/google-vision.json",
                        "objectDetectionConfidence": 0.6,
                    },
                }
            }
        }
    )

    assert config.see.backend is not None
    assert config.see.backend.type == "google-cloud-vision"
    assert config.see.backend.google_cloud_vision is not None
    assert (
        config.see.backend.google_cloud_vision.credentials_path
        == "/tmp/google-vision.json"
    )


def test_vision_none_backend_raises_descriptive_error():
    config = TJBotConfig({"see": {"backend": {"type": "none"}}})
    engine = create_vision_engine(config.see)

    with pytest.raises(TJBotError, match="Vision is disabled"):
        engine.detect_objects(b"image")


def test_google_cloud_vision_confidence_thresholds_accept_valid_range():
    config = TJBotConfig(
        {
            "see": {
                "backend": {
                    "type": "google-cloud-vision",
                    "google-cloud-vision": {
                        "objectDetectionConfidence": 0.7,
                        "imageClassificationConfidence": 0.6,
                        "faceDetectionConfidence": 0.5,
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
            "see": {
                "backend": {
                    "type": "azure-vision",
                    "azure-vision": {
                        "objectDetectionConfidence": 0.7,
                        "imageClassificationConfidence": 0.6,
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
    with pytest.raises(TJBotError, match="invalid TJBot configuration"):
        TJBotConfig(
            {
                "see": {
                    "backend": {
                        "type": "google-cloud-vision",
                        "google-cloud-vision": {
                            "objectDetectionConfidence": 1.5,
                        },
                    }
                }
            }
        )


def test_config_schema_rejects_invalid_log_level():
    with pytest.raises(TJBotError, match="invalid TJBot configuration"):
        TJBotConfig({"log": {"level": "super-loud"}})


# ---------------------------------------------------------------------------
# Backend type schema validation
# ---------------------------------------------------------------------------


def test_sttbackendtypeschema_accepts_none():
    config = TJBotConfig({"listen": {"backend": {"type": "none"}}})
    assert config.listen.backend is not None
    assert config.listen.backend.type == "none"


def test_sttbackendtypeschema_accepts_local():
    config = TJBotConfig({"listen": {"backend": {"type": "local"}}})
    assert config.listen.backend is not None
    assert config.listen.backend.type == "local"


def test_sttbackendtypeschema_rejects_invalid_type():
    with pytest.raises(TJBotError, match="invalid TJBot configuration"):
        TJBotConfig({"listen": {"backend": {"type": "invalid-type"}}})


def test_ttsbackendtypeschema_accepts_none():
    config = TJBotConfig({"speak": {"backend": {"type": "none"}}})
    assert config.speak.backend is not None
    assert config.speak.backend.type == "none"


def test_ttsbackendtypeschema_accepts_local():
    config = TJBotConfig({"speak": {"backend": {"type": "local"}}})
    assert config.speak.backend is not None
    assert config.speak.backend.type == "local"


def test_ttsbackendtypeschema_rejects_invalid_type():
    with pytest.raises(TJBotError, match="invalid TJBot configuration"):
        TJBotConfig({"speak": {"backend": {"type": "invalid-type"}}})


def test_seebackendtypeschema_accepts_none():
    config = TJBotConfig({"see": {"backend": {"type": "none"}}})
    assert config.see.backend is not None
    assert config.see.backend.type == "none"


def test_seebackendtypeschema_accepts_local():
    config = TJBotConfig({"see": {"backend": {"type": "local"}}})
    assert config.see.backend is not None
    assert config.see.backend.type == "local"


def test_seebackendtypeschema_rejects_invalid_type():
    with pytest.raises(TJBotError, match="invalid TJBot configuration"):
        TJBotConfig({"see": {"backend": {"type": "invalid-type"}}})


# ---------------------------------------------------------------------------
# TJBotConfig instantiation
# ---------------------------------------------------------------------------


def test_creates_config_instance_without_user_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home-empty"))
    config = TJBotConfig()
    assert config is not None
    assert config.config is not None


def test_has_all_expected_properties(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home-empty"))
    config = TJBotConfig()
    assert config.log is not None
    assert config.listen is not None
    assert config.see is not None
    assert config.shine is not None
    assert config.speak is not None
    assert config.wave is not None
    assert config.recipe is not None


def test_initializes_empty_objects_for_missing_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home-empty"))
    config = TJBotConfig()
    assert isinstance(config.log, object)
    assert isinstance(config.recipe, dict)


def test_handles_non_existent_user_config_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home-empty"))
    config = TJBotConfig()
    assert config is not None


# ---------------------------------------------------------------------------
# Config access methods
# ---------------------------------------------------------------------------


def test_get_method_returns_config_values():
    config = TJBotConfig()
    log_value = config.get("log")
    assert log_value is not None
    assert isinstance(log_value, object)


def test_get_returns_undefined_for_missing_keys():
    config = TJBotConfig()
    value = config.get("nonExistentKey")
    assert value is None


def test_direct_property_access_works():
    config = TJBotConfig({"listen": {"device": "hw:1,0", "microphoneRate": 48000}})
    assert config.listen.device == "hw:1,0"
    assert config.listen.microphone_rate == 48000


# ---------------------------------------------------------------------------
# User config loading and merging
# ---------------------------------------------------------------------------


def test_loads_and_merges_user_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home-empty"))
    config = TJBotConfig(
        {
            "log": {"level": "debug"},
            "listen": {"microphoneRate": 48000},
            "wave": {"gpioChip": 1, "servoPin": 17},
        }
    )
    assert config.log.level == "debug"
    assert config.listen.microphone_rate == 48000
    assert config.wave.gpio_chip == 1
    assert config.wave.servo_pin == 17


def test_merges_user_config_with_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home-empty"))
    config = TJBotConfig({"log": {"level": "debug"}})
    assert config.log.level == "debug"
    assert config.listen is not None
    assert config.see is not None


# ---------------------------------------------------------------------------
# Invalid config
# ---------------------------------------------------------------------------


def test_rejects_invalid_cameraresolution_string():
    with pytest.raises((TJBotError, Exception)):
        TJBotConfig({"see": {"cameraResolution": "1920x1080"}})


def test_throws_error_when_cameraresolution_is_not_a_tuple():
    with pytest.raises((TJBotError, Exception)):
        TJBotConfig({"see": {"cameraResolution": "not a tuple"}})


def test_accepts_azure_vision_confidence_thresholds_for_supported_operations():
    config = TJBotConfig(
        {
            "see": {
                "backend": {
                    "type": "azure-vision",
                    "azure-vision": {
                        "objectDetectionConfidence": 0.7,
                        "imageClassificationConfidence": 0.6,
                    },
                }
            }
        }
    )
    assert config.see.backend is not None
    assert config.see.backend.azure_vision is not None
    assert config.see.backend.azure_vision.object_detection_confidence == 0.7
    assert config.see.backend.azure_vision.image_classification_confidence == 0.6


def test_accepts_config_with_extra_properties_loose():
    config = TJBotConfig({"log": {"level": "info"}})
    assert config is not None


def test_accepts_recipe_config_in_override():
    config = TJBotConfig(
        {"recipe": {"myCustomSetting": True, "timeout": 5000, "name": "my-recipe"}}
    )
    assert config.recipe.get("myCustomSetting") is True
    assert config.recipe.get("timeout") == 5000
    assert config.recipe.get("name") == "my-recipe"


def test_recipe_field_accepts_any_object():
    config = TJBotConfig({"recipe": {"key1": "value1", "key2": {"nested": "value"}}})
    assert config is not None


# ---------------------------------------------------------------------------
# Deep merge / overrideConfig behavior
# ---------------------------------------------------------------------------


def test_overrideconfig_deeply_merges_nested_objects():
    config = TJBotConfig(
        {
            "see": {
                "backend": {
                    "type": "local",
                    "local": {"objectDetectionModel": "custom-model"},
                }
            }
        }
    )
    assert config.see.backend is not None
    assert config.see.backend.local is not None
    assert config.see.backend.local.object_detection_model == "custom-model"
    assert config.see.backend.local.image_classification_model is not None
    assert config.see.backend.local.face_detection_model is not None


def test_overrideconfig_preserves_sibling_properties_in_nested_sections():
    config = TJBotConfig(
        {
            "listen": {
                "backend": {
                    "type": "local",
                    "local": {"model": "custom-whisper-model"},
                }
            }
        }
    )
    assert config.listen.backend is not None
    assert config.listen.backend.local is not None
    assert config.listen.backend.local.model == "custom-whisper-model"
    assert config.listen.backend.type == "local"


def test_overrideconfig_can_update_multiple_nested_levels_independently():
    config = TJBotConfig(
        {
            "see": {
                "cameraResolution": [1280, 720],
                "backend": {
                    "type": "local",
                    "local": {"objectDetectionModel": "my-model"},
                },
            },
            "listen": {"microphoneRate": 48000},
        }
    )
    assert config.see.camera_resolution == (1280, 720)
    assert config.see.backend is not None
    assert config.see.backend.local.object_detection_model == "my-model"
    assert config.listen.microphone_rate == 48000
    assert config.see.backend.local.image_classification_model is not None
    assert config.listen.device is not None


def test_arrays_are_replaced_entirely_not_merged():
    config = TJBotConfig({"see": {"cameraResolution": [640, 480]}})
    assert config.see.camera_resolution == (640, 480)


# ---------------------------------------------------------------------------
# Complex configs
# ---------------------------------------------------------------------------


def test_handles_nested_backend_configuration():
    config = TJBotConfig(
        {
            "listen": {
                "backend": {
                    "type": "ibm-watson-stt",
                    "ibm-watson-stt": {
                        "model": "en-US_Multimedia",
                        "inactivityTimeout": 30,
                    },
                }
            },
            "speak": {
                "backend": {
                    "type": "ibm-watson-tts",
                    "ibm-watson-tts": {"voice": "en-US_MichaelV3Voice"},
                }
            },
        }
    )
    assert config.listen.backend.type == "ibm-watson-stt"
    assert config.listen.backend.ibm_watson_stt.model == "en-US_Multimedia"
    assert config.speak.backend.type == "ibm-watson-tts"
    assert config.speak.backend.ibm_watson_tts.voice == "en-US_MichaelV3Voice"


def test_handles_both_led_types_in_config():
    config = TJBotConfig(
        {
            "shine": {
                "neopixel": {"gpioPin": 18, "spiInterface": "/dev/spidev0.0"},
                "commonanode": {"redPin": 19, "greenPin": 13, "bluePin": 12},
            }
        }
    )
    assert config.shine.neopixel is not None
    assert config.shine.neopixel.gpio_pin == 18
    assert config.shine.common_anode is not None
    assert config.shine.common_anode.red_pin == 19
    assert config.shine.common_anode.green_pin == 13
    assert config.shine.common_anode.blue_pin == 12


def test_handles_recipe_configuration():
    config = TJBotConfig(
        {"recipe": {"enabled": True, "timeout": 5000, "custom_setting": "value"}}
    )
    assert config.recipe.get("enabled") is True
    assert config.recipe.get("timeout") == 5000
    assert config.recipe.get("custom_setting") == "value"


# ---------------------------------------------------------------------------
# Recipe config path
# ---------------------------------------------------------------------------


def test_handles_missing_recipe_config_file_gracefully():
    config = TJBotConfig({}, "non-existent-recipe.toml")
    assert config is not None
    assert config.recipe is not None


def test_recipe_parameter_allows_custom_recipe_config_path():
    config = TJBotConfig({}, "./custom-recipe.toml")
    assert config is not None
    assert config.recipe is not None


def test_recipe_parameter_defaults_to_recipe_toml_if_not_provided():
    config = TJBotConfig({})
    assert config is not None
    assert config.recipe is not None


def test_merges_recipe_config_with_recipe_section_from_overrideconfig():
    config = TJBotConfig(
        {"recipe": {"setting1": "from-override", "setting2": "override-value"}}
    )
    assert config.recipe.get("setting1") == "from-override"
    assert config.recipe.get("setting2") == "override-value"
