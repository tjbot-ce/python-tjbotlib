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


class RPiDetect:
    """
    Detects Raspberry Pi model.
    """

    @staticmethod
    def model() -> str:
        """
        Get the Raspberry Pi model string.
        """
        # Try device-tree first (most reliable)
        try:
            with open("/proc/device-tree/model", "r") as f:
                model = f.read().strip()
                # Remove null bytes if any
                return model.replace("\0", "")
        except FileNotFoundError:
            pass

        # Fallback to cpuinfo
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("Model"):
                        return line.split(":")[1].strip()
        except FileNotFoundError:
            pass

        return "Unknown"

    @staticmethod
    def is_pi5() -> bool:
        return "Raspberry Pi 5" in RPiDetect.model()

    @staticmethod
    def is_pi4() -> bool:
        return "Raspberry Pi 4" in RPiDetect.model()

    @staticmethod
    def is_pi3() -> bool:
        return "Raspberry Pi 3" in RPiDetect.model()
