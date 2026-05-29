from tjbot.utils.constants import Capability, Hardware


def test_capability_enum_has_all_expected_values():
    assert Capability.LISTEN == "listen"
    assert Capability.SEE == "see"
    assert Capability.SHINE == "shine"
    assert Capability.SPEAK == "speak"
    assert Capability.WAVE == "wave"


def test_capability_enum_values_are_strings():
    for value in Capability:
        assert isinstance(value.value, str)


def test_capability_enum_has_correct_number_of_values():
    assert len(list(Capability)) == 5


def test_capability_enum_values_are_unique():
    values = [value.value for value in Capability]
    assert len(set(values)) == len(values)


def test_capability_can_be_used_as_object_keys():
    capability_map = {
        Capability.LISTEN: True,
        Capability.SPEAK: True,
    }
    assert capability_map[Capability.LISTEN] is True
    assert capability_map[Capability.SPEAK] is True
    assert capability_map.get(Capability.SHINE) is None


def test_hardware_enum_values_are_strings():
    for value in Hardware:
        assert isinstance(value.value, str)


def test_hardware_enum_values_are_unique():
    values = [value.value for value in Hardware]
    assert len(set(values)) == len(values)


def test_hardware_can_be_used_as_object_keys():
    hardware_map = {
        Hardware.CAMERA: True,
        Hardware.SPEAKER: False,
    }
    assert hardware_map[Hardware.CAMERA] is True
    assert hardware_map[Hardware.SPEAKER] is False
    assert hardware_map.get(Hardware.MICROPHONE) is None


def test_all_enums_are_exported_and_accessible():
    assert Capability is not None
    assert Hardware is not None


def test_enum_values_have_no_spaces():
    all_values = [value.value for value in Capability] + [
        value.value for value in Hardware
    ]
    assert all(" " not in value for value in all_values)


def test_enum_values_use_lowercase_or_snake_case():
    all_values = [value.value for value in Capability] + [
        value.value for value in Hardware
    ]
    assert all(value.replace("_", "").islower() for value in all_values)


def test_capability_enums():
    assert Capability.SHINE == "shine"
    assert Capability.LISTEN == "listen"
    assert Capability.SEE == "see"
    assert Capability.WAVE == "wave"
    assert Capability.SPEAK == "speak"


def test_hardware_enums():
    assert Hardware.CAMERA == "camera"
    assert Hardware.LED == "led"
    assert Hardware.MICROPHONE == "microphone"
    assert Hardware.SERVO == "servo"
    assert Hardware.SPEAKER == "speaker"
