import pytest
from tjbot.utils.constants import Capability, Hardware

def test_capability_enums():
    assert Capability.SHINE == 'shine'
    assert Capability.LISTEN == 'listen'
    assert Capability.LOOK == 'look'
    assert Capability.WAVE == 'wave'
    assert Capability.SPEAK == 'speak'

def test_hardware_enums():
    assert Hardware.CAMERA == 'camera'
    assert Hardware.LED_COMMON_ANODE == 'common_anode_led'
    assert Hardware.LED_NEOPIXEL == 'neopixel_led'
    assert Hardware.MICROPHONE == 'microphone'
    assert Hardware.SERVO == 'servo'
    assert Hardware.SPEAKER == 'speaker'

