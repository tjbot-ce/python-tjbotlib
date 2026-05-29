import re
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from .errors import TJBotError

logger = logging.getLogger(__name__)

_color_map: Dict[str, str] = {}
_color_names: List[str] = []
_colors_loaded = False


def _load_colors() -> None:
    global _colors_loaded

    colors_path = Path(__file__).with_name("colors.yaml")
    try:
        with open(colors_path, "r", encoding="utf-8") as file:
            colors = yaml.safe_load(file) or {}

        for name, hex_value in colors.items():
            # YAML 1.1 may coerce unquoted "on"/"off" keys to booleans.
            if isinstance(name, bool):
                color_name = "on" if name else "off"
            else:
                color_name = str(name)

            _color_names.append(color_name)
            normalized_name = re.sub(r"\s+", "", color_name).lower()
            _color_map[normalized_name] = str(hex_value)

        _colors_loaded = True
    except Exception as error:
        logger.error("Failed to load colors.yaml: %s", error)
        raise TJBotError("Failed to load LED color definitions", cause=error)


def _ensure_colors_loaded() -> None:
    if not _colors_loaded:
        _load_colors()


def get_shine_colors() -> List[str]:
    """
    Get the list of all colors recognized by TJBot.
    :return: List of all named colors recognized by ``shine()`` and ``pulse()``.
    """
    _ensure_colors_loaded()
    return list(_color_names)


def convert_hex_to_rgb_color(hex_color: str) -> Tuple[int, int, int]:
    """
    Convert hex color to RGB value.
    :param hex_color: Hex color (e.g. FF8888)
    :return: RGB color (e.g. (255, 128, 128))
    """
    expanded = re.sub(
        r"^#?([a-f\d])([a-f\d])([a-f\d])$",
        r"#\1\1\2\2\3\3",
        hex_color,
        flags=re.IGNORECASE,
    )
    hex_pairs = expanded[1:] if expanded.startswith("#") else expanded

    if len(hex_pairs) != 6:
        logger.warning(
            "An error occurred converting hex color %s to RGB, returning [0, 0, 0]",
            hex_color,
        )
        return (0, 0, 0)

    try:
        rgb = [int(hex_pairs[i : i + 2], 16) for i in (0, 2, 4)]
        return (rgb[0], rgb[1], rgb[2])
    except ValueError:
        logger.warning(
            "An error occurred converting hex color %s to RGB, returning [0, 0, 0]",
            hex_color,
        )
        return (0, 0, 0)


def normalize_color(color: str) -> str:
    """
    Normalize the given color to #RRGGBB.
    :param color: The color name or hex code. May be specified in a number of
        formats, including: hexadecimal (e.g. "0xF12AC4", "11FF22", "#AABB24"),
        "on", "off", or a named color from TJBot's curated LED color list.
        Hexadecimal colors follow a #RRGGBB format.
    :return: Hex string corresponding to the given color (e.g. "#RRGGBB")
    """
    _ensure_colors_loaded()

    norm_color = color if color is not None else "off"

    if norm_color.startswith("0x"):
        norm_color = norm_color[2:]

    if norm_color.startswith("#"):
        norm_color = norm_color[1:]

    is_hex = re.match(r"(^[0-9A-F]{6}$)|(^[0-9A-F]{3}$)", norm_color, re.IGNORECASE)
    rgb = None

    if is_hex:
        # Accept CSS-style short hex (#abc) by expanding to #aabbcc.
        if len(norm_color) == 3:
            norm_color = "".join(ch * 2 for ch in norm_color)
        rgb = norm_color
    else:
        normalized_name = re.sub(r"\s+", "", norm_color).lower()
        if normalized_name == "on":
            rgb = "FFFFFF"
        elif normalized_name == "off":
            rgb = "000000"
        else:
            rgb = _color_map.get(normalized_name)

    if rgb is None:
        raise TJBotError(f'TJBot did not understand the specified color "{color}"')

    if not rgb.startswith("#"):
        rgb = f"#{rgb}"

    if len(rgb) != 7:
        raise TJBotError(f'TJBot did not understand the specified color "{color}"')

    return rgb
