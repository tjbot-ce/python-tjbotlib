from gpiozero import Servo

class TJBotServo:
    """
    Servo controller using gpiozero.
    """

    # Standard servo pulse widths in seconds
    MIN_PULSE_WIDTH = 0.0005  # 500us
    MAX_PULSE_WIDTH = 0.0025  # 2500us

    def __init__(self, pin: int):
        self.servo = Servo(
            pin,
            min_pulse_width=self.MIN_PULSE_WIDTH,
            max_pulse_width=self.MAX_PULSE_WIDTH
        )

    def set_pulse_width(self, pulse_width_ms: float) -> None:
        """
        Set the servo position by pulse width in milliseconds.
        :param pulse_width_ms: Pulse width in milliseconds (e.g. 1.5 for center).
        """
        # Convert ms to seconds
        pulse_width_sec = pulse_width_ms / 1000.0

        # Clamp to min/max to be safe
        pulse_width_sec = max(self.MIN_PULSE_WIDTH, min(self.MAX_PULSE_WIDTH, pulse_width_sec))

        # Convert to -1..1 range for gpiozero.Servo.value
        # value = (pulse - min) / (max - min) * 2 - 1
        # range = max - min

        r = self.MAX_PULSE_WIDTH - self.MIN_PULSE_WIDTH
        value = (pulse_width_sec - self.MIN_PULSE_WIDTH) / r * 2 - 1

        self.servo.value = value

    def cleanup(self) -> None:
        self.servo.close()
