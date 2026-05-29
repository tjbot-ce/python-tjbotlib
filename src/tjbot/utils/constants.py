from enum import StrEnum


class Capability(StrEnum):
    LISTEN = "listen"
    SEE = "see"
    SHINE = "shine"
    SPEAK = "speak"
    WAVE = "wave"


class Hardware(StrEnum):
    CAMERA = "camera"
    LED = "led"
    MICROPHONE = "microphone"
    SERVO = "servo"
    SPEAKER = "speaker"
