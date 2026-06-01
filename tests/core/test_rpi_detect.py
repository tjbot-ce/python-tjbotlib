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

from unittest.mock import patch, mock_open
from tjbot.rpi_drivers.rpi_detect import RPiDetect


def test_detects_raspberry_pi_3_model_correctly():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 3 Model B\0")):
        model = RPiDetect.model()
        assert "Raspberry Pi 3" in model


def test_detects_raspberry_pi_4_model_correctly():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 4 Model B\0")):
        model = RPiDetect.model()
        assert "Raspberry Pi 4" in model


def test_detects_raspberry_pi_5_model_correctly():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 5 Model B\0")):
        model = RPiDetect.model()
        assert "Raspberry Pi 5" in model


def test_returns_a_non_empty_model_string():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 4 Model B\0")):
        model = RPiDetect.model()
        assert isinstance(model, str)
        assert len(model) > 0


def test_model_string_contains_identifying_information():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 4 Model B\0")):
        model = RPiDetect.model()
        assert "Raspberry Pi" in model or "Unknown device" in model


def test_is_pi3_returns_boolean():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 4 Model B\0")):
        assert isinstance(RPiDetect.is_pi3(), bool)


def test_is_pi4_returns_boolean():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 4 Model B\0")):
        assert isinstance(RPiDetect.is_pi4(), bool)


def test_is_pi5_returns_boolean():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 4 Model B\0")):
        assert isinstance(RPiDetect.is_pi5(), bool)


def test_each_pi_version_detector_returns_boolean():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 4 Model B\0")):
        assert isinstance(RPiDetect.is_pi3(), bool)
        assert isinstance(RPiDetect.is_pi4(), bool)
        assert isinstance(RPiDetect.is_pi5(), bool)


def test_pi_version_detection_is_consistent_with_model_string():
    with patch("builtins.open", mock_open(read_data="Raspberry Pi 3 Model B\0")):
        model = RPiDetect.model()
        assert "Raspberry Pi 3" in model


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
