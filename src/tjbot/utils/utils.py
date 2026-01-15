import time
import shutil
import re
import webcolors
from typing import Tuple

from ..error import TJBotError

def sleep(sec: float) -> None:
    """
    Put TJBot to sleep.
    :param sec: Number of seconds to sleep for.
    """
    time.sleep(sec)

def is_command_available(command: str) -> bool:
    """
    Check if a command-line tool is available in PATH.
    :param command: The command to check for.
    :return: True if command is available, False otherwise.
    """
    return shutil.which(command) is not None

def convert_hex_to_rgb_color(hex_color: str) -> Tuple[int, int, int]:
    """
    Convert hex color to RGB value.
    :param hex_color: Hex color (e.g. FF8888)
    :return: RGB color (e.g. (255, 128, 128))
    """
    # Normalize hex string
    hex_color = hex_color.lstrip('#')

    # Expand 3-digit hex to 6-digit
    if len(hex_color) == 3:
        hex_color = ''.join([c * 2 for c in hex_color])

    if len(hex_color) != 6:
        # Default to black/off if invalid, but maybe log warning (Node logs warning)
        return (0, 0, 0)

    try:
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (rgb[0], rgb[1], rgb[2]) # type: ignore
    except ValueError:
        return (0, 0, 0)

def normalize_color(color: str) -> str:
    """
    Normalize the given color to #RRGGBB.
    :param color: The color name or hex code.
    :return: Hex string corresponding to the given color (e.g. "#RRGGBB")
    """
    if not color:
        color = 'off'

    norm_color = color.lower()

    if norm_color == 'on':
        return '#ffffff'
    elif norm_color == 'off':
        return '#000000'

    # Check if it's already a hex code
    if norm_color.startswith('0x'):
        norm_color = norm_color[2:]

    if norm_color.startswith('#'):
        norm_color = norm_color[1:]

    # Is it hex?
    is_hex = re.match(r'^[0-9a-f]{6}$|^[0-9a-f]{3}$', norm_color)

    rgb_hex = None
    if not is_hex:
        try:
            rgb_hex = webcolors.name_to_hex(norm_color)
        except ValueError:
             # Try replacing spaces? or maybe webcolors doesn't cover everything
             # Keep compatibility with TJBotError message
             pass
    else:
        rgb_hex = '#' + norm_color

    if rgb_hex is None:
        raise TJBotError(f'TJBot did not understand the specified color "{color}"')

    # normalize to 6 digits if 3
    rgb_hex = rgb_hex.lower()
    if len(rgb_hex) == 4: # #RGB
        rgb_hex = '#' + ''.join([c*2 for c in rgb_hex[1:]])

    return rgb_hex
