import json
import os
import sys
from pathlib import Path

from logger import logger


class ConnectionsFile:
    file_path = (Path.home() / ".config" / "openvpn3-ubuntu-ui" / "connections.json")

    @classmethod
    def get(cls) -> list[dict]:
        if not cls.file_path.exists():
            return list()

        try:
            with open(cls.file_path) as file:
                return json.load(file)
        except Exception as e:
            logger.exception(e)
            sys.exit(1)

    @classmethod
    def write(cls, connections: list[dict]):
        try:
            os.makedirs(cls.file_path.parent, exist_ok=True)
            with open(cls.file_path, 'w') as file:
                json.dump(connections, file, indent=2)
        except Exception as e:
            logger.exception(e)
            sys.exit(1)
