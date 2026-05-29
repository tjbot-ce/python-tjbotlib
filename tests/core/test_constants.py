import pytest
from tjbot.utils.constants import Capability, Hardware
from tjbot.utils.colors import (
    convert_hex_to_rgb_color,
    get_shine_colors,
    normalize_color,
)


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


def test_normalizes_on_to_white_ffffff():
    assert normalize_color("on") == "#FFFFFF"


def test_normalizes_off_to_black_000000():
    assert normalize_color("off") == "#000000"


def test_normalizes_6_digit_hex_with_hash_prefix():
    assert normalize_color("#FF0000") == "#FF0000"


def test_normalizes_6_digit_hex_without_prefix():
    assert normalize_color("FF0000") == "#FF0000"


def test_throws_tjboterror_for_invalid_color_name():
    with pytest.raises(Exception):
        normalize_color("notarealcolor123")


def test_returns_an_array_of_color_names():
    colors = get_shine_colors()
    assert isinstance(colors, list)
    assert len(colors) > 0


def test_includes_basic_colors_red_green_blue():
    colors = get_shine_colors()
    assert "red" in colors
    assert "green" in colors
    assert "blue" in colors


def test_throws_error_for_color_not_in_curated_list():
    with pytest.raises(Exception):
        normalize_color("chartreuse")


def test_convert_hex_to_rgb():
    assert convert_hex_to_rgb_color("#ffffff") == (255, 255, 255)
    assert convert_hex_to_rgb_color("#000000") == (0, 0, 0)
    assert convert_hex_to_rgb_color("#ff0000") == (255, 0, 0)


def test_normalize_color():
    assert normalize_color("red") == "#FF0000"
    assert normalize_color("blue") == "#0000FF"
    assert normalize_color("green") == "#008000"
    assert normalize_color("#00ff00") == "#00ff00"

    with pytest.raises(Exception):
        normalize_color("invalidcolorname")
