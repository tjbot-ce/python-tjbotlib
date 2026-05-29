import logging
import threading
from typing import Any, Optional, Union

from ..utils.errors import TJBotError
from .servo_constants import MAX_PULSE_MS, MID_PULSE_MS, MIN_PULSE_MS, ServoPosition

logger = logging.getLogger(__name__)

try:
    import lgpio
except ImportError:
    lgpio = None


class LGPIOServoController:
    """Servo controller using lgpio on Raspberry Pi GPIO character devices."""

    def __init__(
        self, chip_number: int, pin: int, freq: int = 50, auto_stop_delay_ms: int = 2000
    ):
        if lgpio is None:
            raise ImportError(
                "lgpio is required for servo control. Install it with: pip install rpi-lgpio"
            )

        self.chip_number = chip_number
        self.pin = pin
        self.freq = freq
        self.chip_handle: Optional[int] = None
        self.claimed = False
        self.current_pulse_ms = MID_PULSE_MS
        self.running = False
        self.auto_stop_timer: Optional[threading.Timer] = None
        self.auto_stop_delay_ms = auto_stop_delay_ms

        logger.debug(
            "LGPIOServoController initialized with config: chip=%s pin=%s frequency=%s Hz",
            chip_number,
            pin,
            freq,
        )

    def set_position(self, position: Union[int, ServoPosition]) -> None:
        pulse_ms = int(position) / 1000.0
        logger.debug("setting servo position to %s us (%s ms)", int(position), pulse_ms)
        self.set_pulse_width(pulse_ms)

    def start(self) -> None:
        try:
            self._ensure_started()
            self._set_servo_pulse(self.current_pulse_ms)
        except Exception:
            logger.exception("ServoController failed to start")
            raise

    def stop(self) -> None:
        logger.debug("stopping LGPIOServoController")
        self.running = False

        if self.auto_stop_timer:
            self.auto_stop_timer.cancel()
            self.auto_stop_timer = None

        if self.claimed and self.chip_handle is not None:
            try:
                module: Any = lgpio
                module.tx_pwm(self.chip_handle, self.pin, self.freq, 0.0, 0, 0)
                module.gpio_write(self.chip_handle, self.pin, 0)
                module.gpio_free(self.chip_handle, self.pin)
                module.gpiochip_close(self.chip_handle)
            except Exception:
                logger.warning("ServoController cleanup warning", exc_info=True)
            finally:
                self.claimed = False
                self.chip_handle = None

    def set_pulse_width(self, pulse_ms: float) -> None:
        self.current_pulse_ms = max(MIN_PULSE_MS, min(MAX_PULSE_MS, pulse_ms))
        self._ensure_started()
        self._set_servo_pulse(self.current_pulse_ms)

        if self.auto_stop_timer:
            self.auto_stop_timer.cancel()
        self.auto_stop_timer = threading.Timer(
            self.auto_stop_delay_ms / 1000.0, self._auto_stop
        )
        self.auto_stop_timer.daemon = True
        self.auto_stop_timer.start()

    def set_angle(self, angle: float) -> None:
        bounded_angle = max(0.0, min(180.0, angle))
        pulse_ms = MIN_PULSE_MS + (bounded_angle / 180.0) * (
            MAX_PULSE_MS - MIN_PULSE_MS
        )
        self.set_pulse_width(pulse_ms)

    def get_pulse_width(self) -> float:
        return self.current_pulse_ms

    def get_angle(self) -> int:
        angle = (
            (self.current_pulse_ms - MIN_PULSE_MS) / (MAX_PULSE_MS - MIN_PULSE_MS)
        ) * 180
        return round(angle)

    def is_running(self) -> bool:
        return self.running

    def cleanup(self) -> None:
        logger.debug("LGPIOServoController cleanup")
        self.stop()

    def _ensure_started(self) -> None:
        if self.running:
            return

        logger.debug("starting LGPIOServoController")
        module: Any = lgpio
        handle = module.gpiochip_open(self.chip_number)
        module.gpio_claim_output(handle, self.pin)
        self.chip_handle = handle
        self.claimed = True
        self.running = True

    def _set_servo_pulse(self, pulse_ms: float) -> None:
        if self.chip_handle is None:
            raise TJBotError("Servo GPIO is not initialized")

        logger.debug("setting servo pulse: %.2f ms", pulse_ms)
        period_ms = 1000.0 / self.freq
        duty_cycle = max(0.0, min(100.0, (pulse_ms / period_ms) * 100.0))
        module: Any = lgpio
        module.tx_pwm(self.chip_handle, self.pin, self.freq, duty_cycle, 0, 0)

    def _auto_stop(self) -> None:
        logger.debug("ServoController auto-stopping after inactivity")
        self.stop()
