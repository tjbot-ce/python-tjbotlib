
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
                return model.replace('\0', '')
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
