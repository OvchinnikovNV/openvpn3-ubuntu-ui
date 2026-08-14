import threading

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from utils.openvpn3 import OpenVPN3


class VpnWorker(QObject):
    connect_started = pyqtSignal(str)
    connect_finished = pyqtSignal(str)
    connect_failed = pyqtSignal(str)
    disconnect_finished = pyqtSignal()
    disconnect_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._cancel_requested = False
        self._lock = threading.Lock()

    def _is_cancelled(self) -> bool:
        with self._lock:
            if self._cancel_requested:
                return True
        return OpenVPN3.is_shutdown_requested()

    def _set_cancelled(self, value: bool) -> None:
        with self._lock:
            self._cancel_requested = value

    @pyqtSlot()
    def cancel_connect(self) -> None:
        self._set_cancelled(True)
        OpenVPN3.request_shutdown()

    @pyqtSlot(str)
    def connect_vpn(self, config_filepath: str) -> None:
        threading.Thread(
            target=self._connect_vpn_impl,
            args=(config_filepath,),
            daemon=True,
        ).start()

    def _connect_vpn_impl(self, config_filepath: str) -> None:
        self._set_cancelled(False)
        OpenVPN3.clear_shutdown()
        OpenVPN3.cleanup_stale_sessions(config_filepath)
        session_path = OpenVPN3.start_session_background(config_filepath)
        if session_path is None:
            if not self._is_cancelled():
                self.connect_failed.emit(OpenVPN3.last_error or 'Connection failed')
            return

        if self._is_cancelled():
            OpenVPN3.disconnect(session_path)
            return

        self.connect_started.emit(session_path)

        if OpenVPN3.wait_for_session_ready(session_path, cancel_check=self._is_cancelled):
            if not self._is_cancelled():
                self.connect_finished.emit(session_path)
            return

        error = OpenVPN3.last_error or 'Connection failed'
        OpenVPN3.disconnect(session_path)
        if self._is_cancelled():
            return
        self.connect_failed.emit(error)

    @pyqtSlot(str)
    def resume_vpn(self, session_path: str) -> None:
        threading.Thread(
            target=self._resume_vpn_impl,
            args=(session_path,),
            daemon=True,
        ).start()

    def _resume_vpn_impl(self, session_path: str) -> None:
        self._set_cancelled(False)
        OpenVPN3.clear_shutdown()
        self.connect_started.emit(session_path)

        if OpenVPN3.wait_for_session_ready(session_path, cancel_check=self._is_cancelled):
            if not self._is_cancelled():
                self.connect_finished.emit(session_path)
            return

        error = OpenVPN3.last_error or 'Connection failed'
        OpenVPN3.disconnect(session_path)
        if self._is_cancelled():
            return
        self.connect_failed.emit(error)

    @pyqtSlot(str)
    def disconnect_vpn(self, session_path: str) -> None:
        threading.Thread(
            target=self._disconnect_vpn_impl,
            args=(session_path,),
            daemon=True,
        ).start()

    def _disconnect_vpn_impl(self, session_path: str) -> None:
        if OpenVPN3.disconnect(session_path):
            self.disconnect_finished.emit()
        else:
            self.disconnect_failed.emit(OpenVPN3.last_error or 'Disconnect failed')
