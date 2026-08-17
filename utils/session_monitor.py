from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from utils.openvpn3 import OpenVPN3, SessionSnapshot


class SessionMonitor(QObject):
    snapshot_ready = pyqtSignal(object)
    config_lookup_ready = pyqtSignal(object)

    @pyqtSlot(str)
    def poll_session(self, session_path: str) -> None:
        self.snapshot_ready.emit(OpenVPN3.snapshot_session(session_path))

    @pyqtSlot(str)
    def lookup_config(self, config_filepath: str) -> None:
        session = OpenVPN3.find_session_for_config(config_filepath)
        if session is None:
            if OpenVPN3.last_list_unavailable():
                return
            self.config_lookup_ready.emit(
                SessionSnapshot(session_path='', session=None, connected=False, pending_auth=False)
            )
            return
        self.config_lookup_ready.emit(OpenVPN3.snapshot_session(session.path))
