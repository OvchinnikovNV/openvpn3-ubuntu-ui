from pathlib import Path

from loguru import logger

logger.add(
    sink=(Path.home() / ".local" / "state" / "openvpn3-ubuntu-ui" / "log.log"),
    format="{time:DD.MM.YYYY at HH:mm:ss} {level} {function} {message}",
    level="INFO",
    rotation="16 MB",
    retention=5,
)
