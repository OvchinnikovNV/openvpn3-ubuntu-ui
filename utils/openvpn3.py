import re
import subprocess

from logger import logger


class OpenVPN3:
    command_timeout = 5

    @classmethod
    def start_session(cls, config_filepath: str) -> str | None:
        result = cls.run_command(['openvpn3', 'session-start', '--config', config_filepath])
        if result is None:
            return None
        match = re.search(r'Session path: (\S+)', result)
        if match is None:
            return None
        return match.group(1)

    @classmethod
    def disconnect(cls, session_path: str) -> bool:
        result = cls.run_command(['openvpn3', 'session-manage', '--disconnect', '--path', session_path])
        if result is None:
            return False
        return bool(re.search(r'Initiated session shutdown\.', result))

    @classmethod
    def auth(cls):
        pass

    @classmethod
    def run_command(cls, command: list[str | int]) -> str | None:
        try:
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=cls.command_timeout,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.exception(f"OpenVPN3: \'{' '.join(command)}\' error: {e}")
        except subprocess.TimeoutExpired:
            logger.error(f"OpenVPN3: \'{' '.join(command)}\' timeout error")
        return None
