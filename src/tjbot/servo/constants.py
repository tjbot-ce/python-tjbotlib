from enum import IntEnum

class ServoPosition(IntEnum):
    ARM_BACK = 700
    ARM_UP = 1400
    ARM_DOWN = 2300
    # Note: These values correspond to pulse width in microseconds
    # Node tjbotlib uses:
    # ARM_BACK = 500
    # ARM_UP = 1400  (This varies in node code, sometimes 1500?)
    # ARM_DOWN = 2300
