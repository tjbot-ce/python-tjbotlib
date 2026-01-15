import pytest
from unittest.mock import patch, mock_open
from tjbot.rpi_drivers.rpi_detect import RPiDetect

def test_detect_rpi5():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 5 Model B\0")):
        assert RPiDetect.is_pi5() is True
        assert RPiDetect.is_pi4() is False
        assert RPiDetect.is_pi3() is False

def test_detect_rpi4():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 4 Model B\0")):
        assert RPiDetect.is_pi5() is False
        assert RPiDetect.is_pi4() is True
        assert RPiDetect.is_pi3() is False

def test_detect_rpi3():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 3 Model B+\0")):
        assert RPiDetect.is_pi5() is False
        assert RPiDetect.is_pi4() is False
        assert RPiDetect.is_pi3() is True

def test_model_string():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 4 Model B\0")):
        model = RPiDetect.model()
        assert "Raspberry Pi 4" in model
