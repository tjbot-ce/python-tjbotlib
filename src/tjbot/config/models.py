from typing import Dict, Literal, Optional, Tuple, Any
from pydantic import BaseModel, Field


class LogConfig(BaseModel):
    level: Optional[str] = "info"


class VADConfig(BaseModel):
    enabled: Optional[bool] = True
    model: Optional[str] = None
    modelUrl: Optional[str] = None


class STTBackendLocalConfig(BaseModel):
    model: Optional[str] = None
    modelUrl: Optional[str] = None
    vad: Optional[VADConfig] = None


class STTBackendIBMWatsonConfig(BaseModel):
    model: Optional[str] = None
    inactivityTimeout: Optional[int] = None
    backgroundAudioSuppression: Optional[float] = None
    interimResults: Optional[bool] = None
    credentialsPath: Optional[str] = None


class STTBackendGoogleCloudConfig(BaseModel):
    model: Optional[str] = None
    languageCode: Optional[str] = None
    credentialsPath: Optional[str] = None
    encoding: Optional[str] = None
    sampleRateHertz: Optional[int] = None
    audioChannelCount: Optional[int] = None
    enableAutomaticPunctuation: Optional[bool] = None
    interimResults: Optional[bool] = None


class STTBackendAzureConfig(BaseModel):
    language: Optional[str] = None
    credentialsPath: Optional[str] = None


class STTBackendConfig(BaseModel):
    type: Optional[Literal['local', 'ibm-watson-stt', 'google-cloud-stt', 'azure-stt']] = 'local'
    local: Optional[STTBackendLocalConfig] = None
    ibm_watson_stt: Optional[STTBackendIBMWatsonConfig] = Field(None, alias="ibm-watson-stt")
    google_cloud_stt: Optional[STTBackendGoogleCloudConfig] = Field(None, alias="google-cloud-stt")
    azure_stt: Optional[STTBackendAzureConfig] = Field(None, alias="azure-stt")


class ListenConfig(BaseModel):
    device: Optional[str] = None
    microphoneRate: Optional[int] = 44100
    microphoneChannels: Optional[int] = 1
    model: Optional[str] = None  # Deprecated in favor of backend.local.model?
    backend: Optional[STTBackendConfig] = None


class SeeConfig(BaseModel):
    cameraResolution: Optional[Tuple[int, int]] = (1920, 1080)
    verticalFlip: Optional[bool] = False
    horizontalFlip: Optional[bool] = False


class LEDNeopixelConfig(BaseModel):
    gpioPin: Optional[int] = None
    spiInterface: Optional[str] = None
    useGRBFormat: Optional[bool] = False


class LEDCommonAnodeConfig(BaseModel):
    redPin: Optional[int] = None
    greenPin: Optional[int] = None
    bluePin: Optional[int] = None


class ShineConfig(BaseModel):
    neopixel: Optional[LEDNeopixelConfig] = None
    commonanode: Optional[LEDCommonAnodeConfig] = None


class TTSBackendLocalConfig(BaseModel):
    model: Optional[str] = None
    modelUrl: Optional[str] = None


class TTSBackendIBMWatsonConfig(BaseModel):
    voice: Optional[str] = None
    credentialsPath: Optional[str] = None


class TTSBackendGoogleCloudConfig(BaseModel):
    voice: Optional[str] = None
    languageCode: Optional[str] = None
    credentialsPath: Optional[str] = None


class TTSBackendAzureConfig(BaseModel):
    voice: Optional[str] = None
    credentialsPath: Optional[str] = None


class TTSBackendConfig(BaseModel):
    type: Optional[Literal['local', 'ibm-watson-tts', 'google-cloud-tts', 'azure-tts']] = 'local'
    local: Optional[TTSBackendLocalConfig] = None
    ibm_watson_tts: Optional[TTSBackendIBMWatsonConfig] = Field(None, alias="ibm-watson-tts")
    google_cloud_tts: Optional[TTSBackendGoogleCloudConfig] = Field(None, alias="google-cloud-tts")
    azure_tts: Optional[TTSBackendAzureConfig] = Field(None, alias="azure-tts")


class SpeakConfig(BaseModel):
    device: Optional[str] = None
    backend: Optional[TTSBackendConfig] = None


class WaveConfig(BaseModel):
    gpioChip: Optional[int] = 0
    servoPin: Optional[int] = 18


class HardwareConfig(BaseModel):
    speaker: Optional[bool] = False
    microphone: Optional[bool] = False
    led_common_anode: Optional[bool] = False
    led_neopixel: Optional[bool] = False
    servo: Optional[bool] = False
    camera: Optional[bool] = False


# TTS & STT Engine configuration (used for TTSEngine & STTEngine constructors)
# These are generic dict types that can hold any configuration data, similar to
# Record<string, unknown> in TypeScript
STTEngineConfig = Dict[str, Any]
TTSEngineConfig = Dict[str, Any]


class TJBotConfigModel(BaseModel):
    log: Optional[LogConfig] = Field(default_factory=LogConfig)
    hardware: Optional[HardwareConfig] = Field(default_factory=HardwareConfig)
    listen: Optional[ListenConfig] = Field(default_factory=ListenConfig)
    see: Optional[SeeConfig] = Field(default_factory=SeeConfig)
    shine: Optional[ShineConfig] = Field(default_factory=ShineConfig)
    speak: Optional[SpeakConfig] = Field(default_factory=SpeakConfig)
    wave: Optional[WaveConfig] = Field(default_factory=WaveConfig)
    recipe: Optional[Dict[str, Any]] = Field(default_factory=dict)
