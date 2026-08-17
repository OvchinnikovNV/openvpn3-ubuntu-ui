import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from logger import logger


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


@dataclass
class VpnSession:
    path: str
    config_name: str
    status: str


@dataclass
class SessionSnapshot:
    session_path: str
    session: VpnSession | None
    connected: bool
    pending_auth: bool
    list_unavailable: bool = False


class OpenVPN3:
    last_error: str | None = None
    _shutdown_requested = False
    _command_lock = threading.Lock()
    _triggered_auth_ids: set[str] = set()
    background_start_timeout = 30
    command_timeout = 15
    auth_command_timeout = 15
    list_timeout = 30
    auth_wait_timeout = 600
    auth_trigger_retries = 20
    auth_retry_interval = 3
    session_missing_threshold = 3
    _last_list_unavailable = False

    SESSION_PATH_RE = re.compile(r'Session path: (\S+)')
    DISCONNECT_SUCCESS_RE = re.compile(r'Initiated session shutdown\.')
    AUTH_REQUEST_RE = re.compile(r'Auth Request:\s*(\d+)')
    CONNECTED_STATUS_RE = re.compile(r'Client connected', re.I)
    AUTH_PENDING_STATUS_RE = re.compile(r'Web authentication', re.I)
    FAILED_STATUS_RE = re.compile(r'authentication failed|connection refused|connection timeout', re.I)
    TRANSIENT_STATUS_RE = re.compile(
        r'\(No status\)|reconnect|reconnecting|pausing|paused|resuming|connecting',
        re.I,
    )

    @classmethod
    def request_shutdown(cls) -> None:
        cls._shutdown_requested = True

    @classmethod
    def clear_shutdown(cls) -> None:
        cls._shutdown_requested = False
        cls._triggered_auth_ids.clear()

    @classmethod
    def cleanup_stale_sessions(cls, config_filepath: str) -> None:
        config_name = Path(config_filepath).name
        sessions = cls.list_sessions()
        if sessions is None:
            return
        for session in sessions:
            if config_name not in session.config_name:
                continue
            if cls._status_is_failed(session.status):
                logger.info(f'Cleaning up stale session {session.path}')
                cls.disconnect(session.path)

    @classmethod
    def is_shutdown_requested(cls) -> bool:
        return cls._shutdown_requested

    @classmethod
    def _should_cancel(cls, cancel_check=None) -> bool:
        if cls._shutdown_requested:
            return True
        return bool(cancel_check and cancel_check())

    @classmethod
    def _interruptible_sleep(cls, seconds: float, cancel_check=None) -> bool:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if cls._should_cancel(cancel_check):
                return True
            time.sleep(0.1)
        return False

    @classmethod
    def start_session_background(cls, config_filepath: str) -> str | None:
        cls.last_error = None
        logger.info(f'Starting VPN session: {config_filepath}')
        result = cls.run_command(
            ['openvpn3', 'session-start', '--config', config_filepath, '--background'],
            timeout=cls.background_start_timeout,
        )
        if result.returncode != 0:
            cls.last_error = cls._format_error(result, 'Failed to start VPN session')
            logger.error(cls.last_error)
            return None
        match = cls.SESSION_PATH_RE.search(result.stdout)
        if match is None:
            cls.last_error = 'Session path not found in openvpn3 output'
            logger.error(cls.last_error)
            return None
        logger.info(f'Session path: {match.group(1)}')
        return match.group(1)

    @classmethod
    def _trigger_web_auth_when_ready(cls, session_path: str, cancel_check=None) -> bool:
        for _ in range(cls.auth_trigger_retries):
            if cls._should_cancel(cancel_check):
                return False
            if cls.trigger_web_auth(session_path, cancel_check=cancel_check):
                return True
            if cls._interruptible_sleep(0.5, cancel_check):
                return False
        return False

    @classmethod
    def last_list_unavailable(cls) -> bool:
        return cls._last_list_unavailable

    @classmethod
    def wait_for_session_ready(cls, session_path: str, cancel_check=None) -> bool:
        cls.last_error = None
        deadline = time.time() + cls.auth_wait_timeout
        last_auth_trigger_at = 0.0
        missing_count = 0
        if cls._should_cancel(cancel_check):
            cls.last_error = 'Connection cancelled'
            return False
        triggered = cls._trigger_web_auth_when_ready(session_path, cancel_check)
        last_auth_trigger_at = time.time() if triggered else 0.0

        while time.time() < deadline:
            if cls._should_cancel(cancel_check):
                cls.last_error = 'Connection cancelled'
                return False

            snapshot = cls.snapshot_session(session_path)
            if snapshot.list_unavailable:
                if cls._interruptible_sleep(2, cancel_check):
                    cls.last_error = 'Connection cancelled'
                    return False
                continue

            if snapshot.connected:
                logger.info(f'Session ready: {session_path}')
                return True

            if snapshot.session is None:
                missing_count += 1
                logger.warning(
                    f'Session temporarily missing ({missing_count}/{cls.session_missing_threshold}): {session_path}'
                )
                if missing_count >= cls.session_missing_threshold:
                    cls.last_error = 'VPN session disappeared during authentication'
                    logger.error(cls.last_error)
                    return False
                if cls._interruptible_sleep(2, cancel_check):
                    cls.last_error = 'Connection cancelled'
                    return False
                continue

            missing_count = 0

            if cls._status_is_failed(snapshot.session.status):
                cls.last_error = snapshot.session.status
                logger.error(f'VPN authentication failed: {cls.last_error}')
                return False

            now = time.time()
            if now - last_auth_trigger_at >= cls.auth_retry_interval:
                cls.trigger_web_auth(session_path, cancel_check=cancel_check)
                last_auth_trigger_at = now

            if cls._interruptible_sleep(2, cancel_check):
                cls.last_error = 'Connection cancelled'
                return False

        cls.last_error = 'Authentication timed out. Complete login in the browser and try again.'
        logger.error(cls.last_error)
        return False

    @classmethod
    def trigger_web_auth(cls, session_path: str | None = None, cancel_check=None) -> bool:
        if cls._should_cancel(cancel_check):
            return False

        result = cls.run_command(['openvpn3', 'session-auth'], timeout=cls.auth_command_timeout)
        if result.returncode != 0:
            logger.warning(cls._format_error(result, 'openvpn3 session-auth failed'))
            return False

        triggered = False
        for block in result.stdout.split('---'):
            if cls._should_cancel(cancel_check):
                return False
            auth_match = cls.AUTH_REQUEST_RE.search(block)
            if auth_match is None:
                continue
            if session_path is not None:
                path_match = re.search(r'Path: (\S+)', block)
                if path_match and path_match.group(1) != session_path:
                    continue
            auth_id = auth_match.group(1)
            auth_key = f'{session_path}:{auth_id}' if session_path else auth_id
            if auth_key in cls._triggered_auth_ids:
                triggered = True
                continue
            auth_result = cls.run_command(
                ['openvpn3', 'session-auth', '--auth-req', auth_id],
                timeout=cls.auth_command_timeout,
            )
            if auth_result.returncode == 0:
                triggered = True
                cls._triggered_auth_ids.add(auth_key)
                logger.info(f'Web authentication browser triggered for request {auth_id}')
            else:
                logger.warning(
                    cls._format_error(
                        auth_result,
                        f'Failed to trigger web auth for request {auth_id}',
                    )
                )
        return triggered

    @classmethod
    def disconnect(cls, session_path: str) -> bool:
        cls.last_error = None
        logger.info(f'Disconnecting session: {session_path}')
        result = cls.run_command(
            ['openvpn3', 'session-manage', '--disconnect', '--path', session_path],
            timeout=cls.command_timeout,
        )
        if result.returncode == 0 and cls.DISCONNECT_SUCCESS_RE.search(result.stdout):
            return True
        if result.returncode == 8:
            return True
        cls.last_error = cls._format_error(result, 'Failed to disconnect VPN session')
        logger.error(cls.last_error)
        return False

    @classmethod
    def list_sessions(cls) -> list[VpnSession] | None:
        cls._last_list_unavailable = False
        result = cls.run_command(
            ['openvpn3', 'sessions-list'],
            timeout=cls.list_timeout,
        )
        if result.returncode != 0:
            cls._last_list_unavailable = True
            logger.warning(cls._format_error(result, 'Failed to list VPN sessions'))
            return None

        sessions: list[VpnSession] = []
        for block in result.stdout.split('---'):
            path_match = re.search(r'Path: (\S+)', block)
            if path_match is None:
                continue
            config_match = re.search(r'Config name: (.+)', block)
            status_match = re.search(r'Status: (.+)', block)
            sessions.append(VpnSession(
                path=path_match.group(1),
                config_name=config_match.group(1).strip() if config_match else '',
                status=status_match.group(1).strip() if status_match else '',
            ))
        return sessions

    @classmethod
    def get_session(cls, session_path: str) -> VpnSession | None:
        return cls.snapshot_session(session_path).session

    @classmethod
    def session_exists(cls, session_path: str) -> bool:
        return cls.snapshot_session(session_path).session is not None

    @classmethod
    def is_session_connected(cls, session_path: str) -> bool:
        return cls.snapshot_session(session_path).connected

    @classmethod
    def is_session_pending_auth(cls, session_path: str) -> bool:
        return cls.snapshot_session(session_path).pending_auth

    @classmethod
    def snapshot_session(cls, session_path: str) -> SessionSnapshot:
        sessions = cls.list_sessions()
        if sessions is None:
            return SessionSnapshot(
                session_path=session_path,
                session=None,
                connected=False,
                pending_auth=False,
                list_unavailable=True,
            )
        for session in sessions:
            if session.path == session_path:
                status = session.status or ''
                return SessionSnapshot(
                    session_path=session_path,
                    session=session,
                    connected=cls._status_is_connected(status),
                    pending_auth=cls._status_is_pending_auth(status),
                )
        return SessionSnapshot(
            session_path=session_path,
            session=None,
            connected=False,
            pending_auth=False,
        )

    @classmethod
    def find_session_for_config(cls, config_filepath: str) -> VpnSession | None:
        config_name = Path(config_filepath).name
        sessions = cls.list_sessions()
        if sessions is None:
            return None
        for session in sessions:
            if config_name in session.config_name:
                return session
        return None

    @classmethod
    def _status_is_connected(cls, status: str) -> bool:
        if cls.CONNECTED_STATUS_RE.search(status):
            return True
        return bool(
            re.search(r'connected', status, re.I)
            and not cls.AUTH_PENDING_STATUS_RE.search(status)
        )

    @classmethod
    def _status_is_pending_auth(cls, status: str) -> bool:
        return bool(cls.AUTH_PENDING_STATUS_RE.search(status))

    @classmethod
    def _status_is_failed(cls, status: str) -> bool:
        return bool(cls.FAILED_STATUS_RE.search(status))

    @classmethod
    def _status_is_transient(cls, status: str) -> bool:
        text = (status or '').strip()
        if not text or text == '(No status)':
            return True
        return bool(cls.TRANSIENT_STATUS_RE.search(text))

    @classmethod
    def _format_error(cls, result: CommandResult, prefix: str) -> str:
        details = result.stderr.strip() or result.stdout.strip()
        if details:
            return f'{prefix}: {details}'
        if result.returncode == -1:
            return f'{prefix}: command timed out'
        return f'{prefix} (exit code {result.returncode})'

    @classmethod
    def run_command(
        cls,
        command: list[str],
        timeout: int | None = None,
    ) -> CommandResult:
        if timeout is None:
            timeout = cls.command_timeout
        with cls._command_lock:
            try:
                proc = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                )
                return CommandResult(proc.stdout, proc.stderr, proc.returncode)
            except subprocess.TimeoutExpired as e:
                stderr = e.stderr or ''
                stdout = e.stdout or ''
                logger.error(f"OpenVPN3: '{' '.join(command)}' timeout after {timeout}s: {stderr.strip()}")
                return CommandResult(stdout, stderr or f'Command timed out after {timeout}s', -1)
