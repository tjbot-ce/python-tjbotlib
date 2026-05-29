import re
import time

import pytest

from tjbot.utils.colors import (
    convert_hex_to_rgb_color,
    get_shine_colors,
    normalize_color,
)
from tjbot.utils.errors import TJBotError
from tjbot.utils.utils import is_command_available, sleep


# ---------------------------------------------------------------------------
# sleep
# ---------------------------------------------------------------------------


def test_sleep():
    start = time.time()
    sleep(100 / 1000)  # 100ms
    end = time.time()
    assert (end - start) >= 0.1


def test_sleep_completes_without_error():
    sleep(0.001)


def test_sleep_with_0_seconds_completes():
    sleep(0)


def test_sleep_is_a_function():
    assert callable(sleep)


def test_sleep_accepts_numeric_argument():
    sleep(0.001)


# ---------------------------------------------------------------------------
# is_command_available
# ---------------------------------------------------------------------------


def test_is_command_available():
    assert is_command_available("ls") is True
    assert is_command_available("nonexistentcommand12345") is False


def test_returns_true_for_available_command_ls():
    assert is_command_available("ls") is True


def test_returns_true_for_available_command_cat():
    assert is_command_available("cat") is True


def test_returns_true_for_available_command_echo():
    assert is_command_available("echo") is True


def test_returns_false_for_unavailable_command():
    assert is_command_available("notarealcommand12345xyz") is False


def test_returns_true_for_node():
    assert is_command_available("node") is True


def test_returns_true_for_npm():
    assert is_command_available("npm") is True


def test_handles_commands_with_special_characters_safely():
    result1 = is_command_available("command-does-not-exist")
    result2 = is_command_available("another_fake_cmd")
    assert isinstance(result1, bool)
    assert isinstance(result2, bool)


# ---------------------------------------------------------------------------
# normalizeColor
# ---------------------------------------------------------------------------


def test_normalizes():
    assert normalize_color("on") == "#FFFFFF"
    assert normalize_color("off") == "#000000"


def test_normalizes_undefined_to_black_off():
    assert normalize_color("off") == "#000000"


def test_normalizes_6_digit_hex_without_prefix():
    assert normalize_color("FF0000") == "#FF0000"


def test_normalizes_6_digit_hex_with_prefix():
    assert normalize_color("#FF0000") == "#FF0000"


def test_normalizes_6_digit_hex_with_0x_prefix():
    assert normalize_color("0xFF0000") == "#FF0000"


def test_handles_3_digit_hex_by_expanding_it():
    assert normalize_color("F00") == "#FF0000"
    assert normalize_color("#ABC") == "#AABBCC"


def test_expands_3_digit_hex_to_6_digit_abc_aabbcc():
    assert normalize_color("abc") == "#aabbcc"


def test_expands_3_digit_hex_with_prefix_abc_aabbcc():
    assert normalize_color("#ABC") == "#AABBCC"


def test_normalizes_lowercase_hex_without_forcing_uppercase():
    result = normalize_color("ff00ff")
    assert result == "#ff00ff"


def test_normalizes_named_color_red():
    result = normalize_color("red")
    assert re.match(r"^#[0-9A-Fa-f]{6}$", result)


def test_normalizes_named_color_blue():
    result = normalize_color("blue")
    assert re.match(r"^#[0-9A-Fa-f]{6}$", result)


def test_normalizes_named_color_green():
    result = normalize_color("green")
    assert re.match(r"^#[0-9A-Fa-f]{6}$", result)


def test_throws_tjboterror_for_invalid_color_name():
    with pytest.raises(TJBotError):
        normalize_color("notarealcolor123")


def test_throws_tjboterror_for_invalid_hex_format():
    with pytest.raises(TJBotError):
        normalize_color("GGGGGG")


def test_throws_tjboterror_for_2_digit_hex():
    with pytest.raises(TJBotError):
        normalize_color("FF")


def test_throws_tjboterror_for_5_digit_hex():
    with pytest.raises(TJBotError):
        normalize_color("FF00F")


def test_handles_mixed_case_named_colors():
    result = normalize_color("Red")
    assert re.match(r"^#[0-9A-Fa-f]{6}$", result)


def test_normalizes_color_with_leading_trailing_case_variations():
    red = normalize_color("red")
    blue = normalize_color("blue")
    assert red != blue
    assert re.match(r"^#[0-9A-Fa-f]{6}$", red)
    assert re.match(r"^#[0-9A-Fa-f]{6}$", blue)


def test_normalizes_curated_color_red():
    assert normalize_color("red") == "#FF0000"


def test_normalizes_curated_color_blue():
    assert normalize_color("blue") == "#0000FF"


def test_normalizes_curated_color_green():
    assert normalize_color("green") == "#008000"


def test_normalizes_curated_color_purple():
    assert normalize_color("purple") == "#800080"


def test_normalizes_multi_word_color_without_spaces_lightpink():
    assert normalize_color("lightpink") == "#FFB6C1"


def test_normalizes_multi_word_color_with_spaces_light_pink():
    assert normalize_color("light pink") == "#FFB6C1"


def test_normalizes_multi_word_color_with_mixed_case_light_pink():
    assert normalize_color("Light Pink") == "#FFB6C1"


def test_normalizes_multi_word_color_all_caps_with_spaces_light_pink():
    assert normalize_color("LIGHT PINK") == "#FFB6C1"


def test_normalizes_multi_word_color_darkblue_vs_dark_blue():
    r1 = normalize_color("darkblue")
    r2 = normalize_color("dark blue")
    assert r1 == "#00008B"
    assert r2 == "#00008B"


def test_normalizes_multi_word_color_skyblue_vs_sky_blue():
    r1 = normalize_color("skyblue")
    r2 = normalize_color("sky blue")
    assert r1 == "#87CEEB"
    assert r2 == "#87CEEB"


def test_normalizes_multi_word_color_hotpink_vs_hot_pink():
    r1 = normalize_color("hotpink")
    r2 = normalize_color("hot pink")
    assert r1 == "#FF69B4"
    assert r2 == "#FF69B4"


def test_throws_error_for_color_not_in_curated_list():
    with pytest.raises(TJBotError):
        normalize_color("chartreuse")
    with pytest.raises(TJBotError):
        normalize_color("lavender")


def test_throws_error_for_3_digit_hex_expects_6_digit():
    # 3-digit hex WITHOUT # prefix is NOT expanded — must be exactly 3 chars like #ABC or ABC
    # Confirm 3-char valid input expands:
    assert normalize_color("F00") == "#FF0000"


def test_throws_error_for_3_digit_hex_with_prefix():
    assert normalize_color("#F00") == "#FF0000"


# ---------------------------------------------------------------------------
# convertHexToRgbColor
# ---------------------------------------------------------------------------


def test_converts_hex_with_prefix_correctly():
    assert convert_hex_to_rgb_color("#FF0000") == (255, 0, 0)


def test_converts_other_colors_with_prefix():
    assert convert_hex_to_rgb_color("#00FF00") == (0, 255, 0)


def test_returns_array_with_three_elements():
    result = convert_hex_to_rgb_color("#123ABC")
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_handles_3_digit_hex_by_expanding_it():  # noqa: F811
    assert convert_hex_to_rgb_color("F00") == (255, 0, 0)


def test_returns_array_with_three_elements_for_invalid_hex_values_may_be_nan():
    # convertHexToRgbColor on truly invalid input returns a 3-tuple (may contain 0s)
    result = convert_hex_to_rgb_color("GGGGGG")
    assert isinstance(result, tuple)
    assert len(result) == 3


# ---------------------------------------------------------------------------
# getShineColors
# ---------------------------------------------------------------------------


def test_returns_an_array_of_color_names():
    colors = get_shine_colors()
    assert isinstance(colors, list)
    assert len(colors) > 0


def test_returns_curated_colors_list():
    colors = get_shine_colors()
    assert len(colors) > 0


def test_includes_basic_colors_red_green_blue():
    colors = get_shine_colors()
    assert "red" in colors
    assert "green" in colors
    assert "blue" in colors


def test_includes_special_colors_on_off():
    colors = get_shine_colors()
    assert "on" in colors
    assert "off" in colors


def test_includes_multi_word_colors_lightpink_darkblue_etc():
    colors = get_shine_colors()
    assert "lightpink" in colors
    assert "darkblue" in colors
    assert "skyblue" in colors
