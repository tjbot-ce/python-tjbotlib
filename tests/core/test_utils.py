import pytest
import time
from tjbot.utils.utils import (
    sleep,
    is_command_available,
    convert_hex_to_rgb_color,
    normalize_color
)

def test_sleep():
    start = time.time()
    sleep(100/1000) # 100ms
    end = time.time()
    assert (end - start) >= 0.1

def test_convert_hex_to_rgb():
    assert convert_hex_to_rgb_color('#ffffff') == (255, 255, 255)
    assert convert_hex_to_rgb_color('#000000') == (0, 0, 0)
    assert convert_hex_to_rgb_color('#ff0000') == (255, 0, 0)

def test_normalize_color():
    assert normalize_color('red') == '#ff0000'
    assert normalize_color('blue') == '#0000ff'
    assert normalize_color('green') == '#008000'
    assert normalize_color('#00ff00') == '#00ff00'

    with pytest.raises(Exception):
        normalize_color('invalidcolorname')

def test_is_command_available():
    # Only test common commands likely to exist or not
    assert is_command_available('ls') is True
    assert is_command_available('nonexistentcommand12345') is False
