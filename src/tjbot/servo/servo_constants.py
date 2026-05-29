from enum import IntEnum


class ServoPosition(IntEnum):
    ARM_BACK = 700
    ARM_UP = 1400
    ARM_DOWN = 2300


MIN_PULSE_MS = 0.5
MID_PULSE_MS = 1.5
MAX_PULSE_MS = 2.5
