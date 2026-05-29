import logging
from enum import StrEnum
from typing import Optional


class LogEmoji(StrEnum):
    CAMERA = "📷"
    COLOR = "🎨"
    CONFIG = "⚙️"
    GENERAL = "🤖"
    HARDWARE = "🔧"
    LED = "💡"
    MIC = "🎤"
    MODEL = "📦"
    RPI = "🍓"
    SERVO = "🦾"
    SPEAKER = "🔈"
    STT = "🦻"
    TTS = "💬"
    VISION = "👁️"


TJBotLogLevel = str

_PACKAGE_LOGGER = "tjbot"
_configured = False

_LOG_LEVEL_MAP: dict[str, int] = {
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "info": logging.INFO,
    "verbose": logging.DEBUG,
    "debug": logging.DEBUG,
    "silly": logging.DEBUG,
}

_LOGGER_NAME_EMOJI_RULES: tuple[tuple[str, LogEmoji], ...] = (
    (".camera", LogEmoji.CAMERA),
    (".config", LogEmoji.CONFIG),
    (".led", LogEmoji.LED),
    (".microphone", LogEmoji.MIC),
    (".rpi_drivers", LogEmoji.RPI),
    (".servo", LogEmoji.SERVO),
    (".speaker", LogEmoji.SPEAKER),
    (".stt", LogEmoji.STT),
    (".tts", LogEmoji.TTS),
    (".vision", LogEmoji.VISION),
    ("model_registry", LogEmoji.MODEL),
    ("normalize_color", LogEmoji.COLOR),
)


def _to_python_log_level(level: Optional[TJBotLogLevel]) -> int:
    if not level:
        return logging.INFO
    return _LOG_LEVEL_MAP.get(level.lower(), logging.INFO)


def _emoji_for_logger_name(logger_name: str) -> LogEmoji:
    normalized = logger_name.lower()
    for pattern, emoji in _LOGGER_NAME_EMOJI_RULES:
        if pattern in normalized:
            return emoji
    return LogEmoji.GENERAL


class TJBotLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        emoji = _emoji_for_logger_name(record.name)
        level = record.levelname.lower()
        message = record.getMessage()
        base = f"{level}: {emoji} {message}"

        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"

        return base


def init_logging(level: TJBotLogLevel = "info") -> None:
    global _configured

    package_logger = logging.getLogger(_PACKAGE_LOGGER)
    package_logger.setLevel(_to_python_log_level(level))
    package_logger.propagate = True

    if not _configured:
        handler = logging.StreamHandler()
        handler.setFormatter(TJBotLogFormatter())
        package_logger.handlers.clear()
        package_logger.addHandler(handler)
        _configured = True


def set_log_level(level: TJBotLogLevel) -> None:
    init_logging(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
