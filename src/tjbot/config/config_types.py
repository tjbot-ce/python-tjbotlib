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

from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


class TJBotBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class LogConfig(TJBotBaseModel):
    level: Optional[str] = "info"


class VADConfig(TJBotBaseModel):
    enabled: Optional[bool] = True
    model: Optional[str] = None
    model_url: Optional[str] = Field(default=None, alias="modelUrl")


class STTBackendLocalConfig(TJBotBaseModel):
    model: Optional[str] = None
    model_url: Optional[str] = Field(default=None, alias="modelUrl")
    vad: Optional[VADConfig] = None


class STTBackendIBMWatsonConfig(TJBotBaseModel):
    model: Optional[str] = None
    inactivity_timeout: Optional[int] = Field(default=None, alias="inactivityTimeout")
    background_audio_suppression: Optional[float] = Field(
        default=None, alias="backgroundAudioSuppression"
    )
    interim_results: Optional[bool] = Field(default=None, alias="interimResults")
    credentials_path: Optional[str] = Field(default=None, alias="credentialsPath")


class STTBackendGoogleCloudConfig(TJBotBaseModel):
    model: Optional[str] = None
    language_code: Optional[str] = Field(default=None, alias="languageCode")
    credentials_path: Optional[str] = Field(default=None, alias="credentialsPath")
    encoding: Optional[str] = None
    sample_rate_hertz: Optional[int] = Field(default=None, alias="sampleRateHertz")
    audio_channel_count: Optional[int] = Field(default=None, alias="audioChannelCount")
    enable_automatic_punctuation: Optional[bool] = Field(
        default=None, alias="enableAutomaticPunctuation"
    )
    interim_results: Optional[bool] = Field(default=None, alias="interimResults")
    region: Optional[str] = None
    profanity_filter: Optional[bool] = Field(default=None, alias="profanityFilter")


class STTBackendAzureConfig(TJBotBaseModel):
    language: Optional[str] = None
    credentials_path: Optional[str] = Field(default=None, alias="credentialsPath")
    interim_results: Optional[bool] = Field(default=None, alias="interimResults")


class STTBackendConfig(TJBotBaseModel):
    type: Optional[
        Literal["none", "local", "ibm-watson-stt", "google-cloud-stt", "azure-stt"]
    ] = "local"
    local: Optional[STTBackendLocalConfig] = None
    ibm_watson_stt: Optional[STTBackendIBMWatsonConfig] = Field(
        default=None, alias="ibm-watson-stt"
    )
    google_cloud_stt: Optional[STTBackendGoogleCloudConfig] = Field(
        default=None, alias="google-cloud-stt"
    )
    azure_stt: Optional[STTBackendAzureConfig] = Field(default=None, alias="azure-stt")


class ListenConfig(TJBotBaseModel):
    device: Optional[str] = None
    microphone_rate: Optional[int] = Field(default=44100, alias="microphoneRate")
    microphone_channels: Optional[int] = Field(default=2, alias="microphoneChannels")
    model: Optional[str] = None
    backend: Optional[STTBackendConfig] = None


class SeeBackendLocalConfig(TJBotBaseModel):
    object_detection_model: Optional[str] = Field(
        default=None, alias="objectDetectionModel"
    )
    image_classification_model: Optional[str] = Field(
        default=None, alias="imageClassificationModel"
    )
    face_detection_model: Optional[str] = Field(
        default=None, alias="faceDetectionModel"
    )
    object_detection_confidence: Optional[float] = Field(
        default=None, alias="objectDetectionConfidence"
    )
    image_classification_confidence: Optional[float] = Field(
        default=None, alias="imageClassificationConfidence"
    )
    face_detection_confidence: Optional[float] = Field(
        default=None, alias="faceDetectionConfidence"
    )


class SeeBackendGoogleCloudConfig(TJBotBaseModel):
    credentials_path: Optional[str] = Field(default=None, alias="credentialsPath")
    object_detection_confidence: Optional[float] = Field(
        default=None, alias="objectDetectionConfidence"
    )
    image_classification_confidence: Optional[float] = Field(
        default=None, alias="imageClassificationConfidence"
    )
    face_detection_confidence: Optional[float] = Field(
        default=None, alias="faceDetectionConfidence"
    )


class SeeBackendAzureConfig(TJBotBaseModel):
    credentials_path: Optional[str] = Field(default=None, alias="credentialsPath")
    object_detection_confidence: Optional[float] = Field(
        default=None, alias="objectDetectionConfidence"
    )
    image_classification_confidence: Optional[float] = Field(
        default=None, alias="imageClassificationConfidence"
    )


class SeeBackendConfig(TJBotBaseModel):
    type: Optional[Literal["none", "local", "google-cloud-vision", "azure-vision"]] = (
        "none"
    )
    local: Optional[SeeBackendLocalConfig] = None
    google_cloud_vision: Optional[SeeBackendGoogleCloudConfig] = Field(
        default=None, alias="google-cloud-vision"
    )
    azure_vision: Optional[SeeBackendAzureConfig] = Field(
        default=None, alias="azure-vision"
    )


class SeeConfig(TJBotBaseModel):
    camera_resolution: Optional[Tuple[int, int]] = Field(
        default=(1920, 1080), alias="cameraResolution"
    )
    vertical_flip: Optional[bool] = Field(default=False, alias="verticalFlip")
    horizontal_flip: Optional[bool] = Field(default=False, alias="horizontalFlip")
    capture_timeout: Optional[int] = Field(default=None, alias="captureTimeout")
    zero_shutter_lag: Optional[bool] = Field(default=None, alias="zeroShutterLag")
    backend: Optional[SeeBackendConfig] = None


class LEDNeopixelConfig(TJBotBaseModel):
    gpio_pin: Optional[int] = Field(default=None, alias="gpioPin")
    spi_interface: Optional[str] = Field(default=None, alias="spiInterface")
    use_grb_format: Optional[bool] = Field(default=False, alias="useGRBFormat")


class LEDCommonAnodeConfig(TJBotBaseModel):
    red_pin: Optional[int] = Field(default=None, alias="redPin")
    green_pin: Optional[int] = Field(default=None, alias="greenPin")
    blue_pin: Optional[int] = Field(default=None, alias="bluePin")


class ShineConfig(TJBotBaseModel):
    has_neopixel_led: Optional[bool] = Field(default=False, alias="hasNeopixelLED")
    has_common_anode_led: Optional[bool] = Field(
        default=False, alias="hasCommonAnodeLED"
    )
    neopixel: Optional[LEDNeopixelConfig] = None
    common_anode: Optional[LEDCommonAnodeConfig] = Field(
        default=None, alias="commonanode"
    )


class TTSBackendLocalConfig(TJBotBaseModel):
    model: Optional[str] = None
    model_url: Optional[str] = Field(default=None, alias="modelUrl")


class TTSBackendIBMWatsonConfig(TJBotBaseModel):
    voice: Optional[str] = None
    credentials_path: Optional[str] = Field(default=None, alias="credentialsPath")


class TTSBackendGoogleCloudConfig(TJBotBaseModel):
    voice: Optional[str] = None
    language_code: Optional[str] = Field(default=None, alias="languageCode")
    credentials_path: Optional[str] = Field(default=None, alias="credentialsPath")


class TTSBackendAzureConfig(TJBotBaseModel):
    voice: Optional[str] = None
    credentials_path: Optional[str] = Field(default=None, alias="credentialsPath")


class TTSBackendConfig(TJBotBaseModel):
    type: Optional[
        Literal["none", "local", "ibm-watson-tts", "google-cloud-tts", "azure-tts"]
    ] = "local"
    local: Optional[TTSBackendLocalConfig] = None
    ibm_watson_tts: Optional[TTSBackendIBMWatsonConfig] = Field(
        default=None, alias="ibm-watson-tts"
    )
    google_cloud_tts: Optional[TTSBackendGoogleCloudConfig] = Field(
        default=None, alias="google-cloud-tts"
    )
    azure_tts: Optional[TTSBackendAzureConfig] = Field(default=None, alias="azure-tts")


class SpeakConfig(TJBotBaseModel):
    device: Optional[str] = None
    backend: Optional[TTSBackendConfig] = None


class WaveConfig(TJBotBaseModel):
    gpio_chip: Optional[int] = Field(default=0, alias="gpioChip")
    servo_pin: Optional[int] = Field(default=18, alias="servoPin")


class HardwareConfig(TJBotBaseModel):
    speaker: Optional[bool] = False
    microphone: Optional[bool] = False
    led: Optional[bool] = False
    servo: Optional[bool] = False
    camera: Optional[bool] = False


STTEngineConfig = Dict[str, Any]
TTSEngineConfig = Dict[str, Any]


class TJBotConfigSchema(TJBotBaseModel):
    log: Optional[LogConfig] = Field(default_factory=LogConfig)
    hardware: Optional[HardwareConfig] = Field(default_factory=HardwareConfig)
    listen: Optional[ListenConfig] = Field(default_factory=ListenConfig)
    see: Optional[SeeConfig] = Field(default_factory=SeeConfig)
    shine: Optional[ShineConfig] = Field(default_factory=ShineConfig)
    speak: Optional[SpeakConfig] = Field(default_factory=SpeakConfig)
    wave: Optional[WaveConfig] = Field(default_factory=WaveConfig)
    recipe: Optional[Dict[str, Any]] = Field(default_factory=dict)
    models: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
