from enum import StrEnum

class Capability(StrEnum):
    LISTEN = 'listen'
    LOOK = 'look'
    SHINE = 'shine'
    SPEAK = 'speak'
    WAVE = 'wave'

class Hardware(StrEnum):
    CAMERA = 'camera'
    LED_COMMON_ANODE = 'common_anode_led'
    LED_NEOPIXEL = 'neopixel_led'
    MICROPHONE = 'microphone'
    SERVO = 'servo'
    SPEAKER = 'speaker'


