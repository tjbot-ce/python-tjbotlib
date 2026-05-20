import time
from typing import List

try:
    import spidev  # type: ignore
except ImportError:
    spidev = None


class LEDNeopixelSPI:
    """
    LED controller for SPI-based NeoPixel LEDs (Raspberry Pi 5).
    This is based on pi5neo.py:
    https://github.com/vanshksingh/Pi5Neo/blob/main/pi5neo/pi5neo.py
    """
    HIGH = 0xf8  # possibles: F0, F8, FC
    LOW = 0xc0   # possibles: C0
    FREQ = 6400000  # possibles: 3200000, 6400000; pi5neo uses: spi_speed_khz (800) * 1024 * 8 = 6553600

    def __init__(self, spi_interface: str = '/dev/spidev0.0', use_grb_format: bool = False):
        if spidev is None:
            raise ImportError("spidev library not found. Please install it.")

        self.use_grb_format = use_grb_format

        # Parse spi interface string "/dev/spidevX.Y"
        try:
            parts = spi_interface.split('spidev')[1].split('.')
            bus = int(parts[0])
            device = int(parts[1])
        except (IndexError, ValueError):
            # Fallback defaults
            bus = 0
            device = 0

        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = self.FREQ

    @staticmethod
    def _byte_to_bitstream(byte: int) -> List[int]:
        bitstream = []
        for i in range(8):
            # MSB first
            if (byte & (1 << (7 - i))) != 0:
                bitstream.append(LEDNeopixelSPI.HIGH)
            else:
                bitstream.append(LEDNeopixelSPI.LOW)
        return bitstream

    @staticmethod
    def _rgb_to_spi_bitstream(red: int, green: int, blue: int, use_grb: bool) -> List[int]:
        red_bits = LEDNeopixelSPI._byte_to_bitstream(red)
        green_bits = LEDNeopixelSPI._byte_to_bitstream(green)
        blue_bits = LEDNeopixelSPI._byte_to_bitstream(blue)

        if use_grb:
            return green_bits + red_bits + blue_bits
        else:
            return red_bits + green_bits + blue_bits

    def render(self, color: str) -> None:
        """
        Render the LED to a specified color.
        :param color: Hex color string in RRGGBB format with no leading '0x' or '#'.

        Note: This method blocks until the SPI transfer completes to ensure
        timing integrity of the WS2812B protocol on RPi 5.
        """
        c = int(color, 16)
        r = (c & 0xff0000) >> 16
        g = (c & 0x00ff00) >> 8
        b = (c & 0x0000ff) >> 0

        bitstream = self._rgb_to_spi_bitstream(r, g, b, self.use_grb_format)

        # Transfer data via SPI to update the LED.
        # The writebytes() call blocks until the transfer completes.
        self.spi.writebytes(bitstream)

        # Add delay to ensure the SPI transfer is fully complete and the LED
        # has latched the data. WS2812B requires ~50µs reset time minimum,
        # but we use 10ms to account for SPI overhead and ensure stability.
        time.sleep(0.01)  # 10ms delay for reliable data latching

    def cleanup(self) -> None:
        if self.spi:
            self.spi.close()
