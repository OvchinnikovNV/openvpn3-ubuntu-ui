import threading
from pathlib import Path

from PyQt6.QtCore import QThread, QTimer, QMetaObject, Qt, Q_ARG, QEvent
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QMainWindow, QMessageBox

from ui.pyuic.mainwindow import Ui_MainWindow
from ui.styles import STATUS_COLORS, STATUS_DOT_STYLE, connect_button_style
from utils.connections_file import ConnectionsFile
from utils.enums import ConnectButtonText, VpnUiState
from utils.openvpn3 import OpenVPN3, SessionSnapshot
from utils.session_monitor import SessionMonitor
from utils.vpn_worker import VpnWorker
from widgets.manager import Manager
from logger import logger


class MainWindow(QMainWindow):
    SESSION_POLL_INTERVAL_MS = 10000

    _STATUS_LABELS = {
        VpnUiState.disconnected: ("Disconnected", "Select a profile and press Connect"),
        VpnUiState.connecting: ("Connecting", "Starting VPN session..."),
        VpnUiState.authenticating: ("Authenticating", "Complete login in browser, or press Cancel"),
        VpnUiState.connected: ("Connected", "Your connection is secure"),
        VpnUiState.disconnecting: ("Disconnecting", "Closing VPN session..."),
    }

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setFixedSize(340, 420)

        self.ui.btn_connect.setText(ConnectButtonText.connect.value)
        self.ui.btn_connect.setFixedSize(120, 120)
        self.ui.btn_connect.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.current_connection: dict[str, str] | None = None
        self.session_path: str | None = None
        self._busy = False
        self._connecting = False
        self._ui_state = VpnUiState.disconnected
        self._shutting_down = False
        self._cancelled_by_user = False
        self._last_snapshot: SessionSnapshot | None = None

        self.connections = ConnectionsFile.get()

        self._worker_thread = QThread(self)
        self._worker = VpnWorker()
        self._worker.moveToThread(self._worker_thread)
        self._worker.connect_started.connect(self._on_connect_started)
        self._worker.connect_finished.connect(self._on_connect_finished)
        self._worker.connect_failed.connect(self._on_connect_failed)
        self._worker.disconnect_finished.connect(self._on_disconnect_finished)
        self._worker.disconnect_failed.connect(self._on_disconnect_failed)
        self._worker_thread.start()

        self._monitor_thread = QThread(self)
        self._session_monitor = SessionMonitor()
        self._session_monitor.moveToThread(self._monitor_thread)
        self._session_monitor.snapshot_ready.connect(self._on_session_snapshot)
        self._session_monitor.config_lookup_ready.connect(self._on_config_lookup)
        self._monitor_thread.start()

        self._session_poll_timer = QTimer(self)
        self._session_poll_timer.setInterval(self.SESSION_POLL_INTERVAL_MS)
        self._session_poll_timer.timeout.connect(self._on_session_poll)

        self.connect_slots()
        self._setup_window_drag()
        self.update_cbox_connections()
        self._set_ui_state(VpnUiState.disconnected)
        self._sync_existing_session()

    def connect_slots(self):
        self.ui.toolbtn_manage.clicked.connect(self.on_toolbtn_manage)
        self.ui.cbox_connections.currentIndexChanged.connect(self.on_cbox_connections_index_changed)
        self.ui.btn_connect.clicked.connect(self.on_btn_connect)

    def _setup_window_drag(self):
        self._drag_widgets = (
            self.ui.lbl_title,
            self.ui.lbl_subtitle,
            self.ui.lbl_section,
            self.ui.status_card,
            self.ui.lbl_status,
            self.ui.lbl_status_hint,
            self.ui.lbl_status_dot,
            self.ui.lbl_profile_active,
        )
        for widget in self._drag_widgets:
            widget.setCursor(Qt.CursorShape.OpenHandCursor)
            widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj not in self._drag_widgets:
            return super().eventFilter(obj, event)
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            window_handle = self.windowHandle()
            if window_handle is not None:
                window_handle.startSystemMove()
            return False
        return super().eventFilter(obj, event)

    def _profile_name(self) -> str:
        if self.current_connection is None:
            return '#UNKNOWN'
        return self.current_connection.get('name', '#UNKNOWN')

    def on_manager_connections_changed(self, connections: list[dict]):
        self.connections = connections.copy()
        self.update_cbox_connections()

    def on_toolbtn_manage(self):
        manager = Manager(self.connections, parent=self)
        manager.emitter.connections_changed.connect(self.on_manager_connections_changed)
        manager.exec()

    def on_cbox_connections_index_changed(self, i: int):
        if i == -1:
            self.current_connection = None
            self._update_controls()
            return

        try:
            self.current_connection = self.connections[i]
        except IndexError as e:
            logger.exception(e)
            self.current_connection = None
            self._show_error(
                'Profile error',
                'Selected profile is no longer available. Open Manage to refresh the list.',
            )
            self.update_cbox_connections()
            return

        self._sync_existing_session()

    def on_btn_connect(self):
        if self._busy and self._connecting:
            self._request_cancel_connect()
            return

        if self._busy:
            return

        btn_connect_text = self.ui.btn_connect.text()

        if btn_connect_text == ConnectButtonText.connect.value:
            if self.current_connection is None:
                return
            config_filepath = self.current_connection.get('file', '')
            if not config_filepath:
                return
            if not Path(config_filepath).is_file():
                self._show_error(
                    'Profile not found',
                    f'Configuration file not found:\n{config_filepath}',
                )
                return

            self._cancelled_by_user = False
            self._set_busy(True)
            self._update_profile_display()
            self._set_ui_state(VpnUiState.connecting)
            self._session_poll_timer.start()
            logger.info(f'Connect requested for {self._profile_name()}: {config_filepath}')
            QMetaObject.invokeMethod(
                self._worker,
                'connect_vpn',
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, config_filepath),
            )

        elif btn_connect_text == ConnectButtonText.disconnect.value:
            if self.session_path is None:
                self._apply_disconnected_state()
                return

            self._set_busy(True)
            self._set_ui_state(VpnUiState.disconnecting)
            logger.info(f'Disconnect requested for {self._profile_name()}: {self.session_path}')
            QMetaObject.invokeMethod(
                self._worker,
                'disconnect_vpn',
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, self.session_path),
            )

    def _request_cancel_connect(self):
        logger.info('Connection cancelled by user')
        self._cancelled_by_user = True
        self._session_poll_timer.stop()
        OpenVPN3.request_shutdown()
        QMetaObject.invokeMethod(
            self._worker,
            'cancel_connect',
            Qt.ConnectionType.QueuedConnection,
        )
        self.session_path = None
        self._connecting = False
        self._busy = False
        self._update_profile_display()
        self._set_ui_state(VpnUiState.disconnected)
        self._update_controls()

    def _on_connect_started(self, session_path: str):
        if self._cancelled_by_user:
            return
        self.session_path = session_path
        self._connecting = True
        logger.info(f'Session started: {session_path}')
        self._update_profile_display()
        self._set_ui_state(VpnUiState.authenticating)

    def _on_connect_finished(self, session_path: str):
        if self._cancelled_by_user:
            self._cancelled_by_user = False
            return
        self._set_busy(False)
        self._connecting = False
        logger.success(f'Connected to {self._profile_name()}!')
        self._apply_connected_state(session_path)
        self._session_poll_timer.start()

    def _on_connect_failed(self, error: str):
        if self._cancelled_by_user:
            self._cancelled_by_user = False
            return
        self._set_busy(False)
        self._connecting = False
        self._session_poll_timer.stop()
        logger.error(f'Connection failed: {error}')
        self._show_error('Connection failed', error)
        if self.session_path is not None:
            self._cleanup_session_async(self.session_path)
        self._update_profile_display()
        self._apply_disconnected_state()
        self._sync_existing_session()

    def _on_disconnect_finished(self):
        self._set_busy(False)
        logger.success(f'Disconnected from {self._profile_name()}!')
        self._apply_disconnected_state()

    def _on_disconnect_failed(self, error: str):
        self._set_busy(False)
        logger.error(f"Disconnect failed: {error}")
        if self.session_path and self._last_snapshot and self._last_snapshot.session is None:
            self._apply_disconnected_state()
            return
        self._set_ui_state(VpnUiState.connected)
        self._show_error('Disconnect failed', error)

    def _on_session_poll(self):
        if self.session_path is None or self._connecting:
            return
        QMetaObject.invokeMethod(
            self._session_monitor,
            'poll_session',
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, self.session_path),
        )

    def _on_session_snapshot(self, snapshot: SessionSnapshot):
        if self._shutting_down or self.session_path is None:
            return
        if snapshot.session_path != self.session_path:
            return

        if snapshot.list_unavailable:
            return

        self._last_snapshot = snapshot

        if snapshot.connected:
            if self._connecting:
                self._connecting = False
                self._set_busy(False)
                self._apply_connected_state(self.session_path)
                self._session_poll_timer.start()
            else:
                self._refresh_connected_hint()
            return

        if snapshot.session is None:
            if self._connecting:
                return
            logger.warning('VPN session lost, resetting UI')
            self._apply_disconnected_state(notify=True)
            return

        if snapshot.pending_auth:
            if not self._connecting:
                self._set_ui_state(VpnUiState.authenticating)
            return

        if self._connecting:
            return

        status = snapshot.session.status or ''
        if OpenVPN3._status_is_transient(status):
            logger.info(f'VPN session temporary status: {status or "(empty)"}')
            return

        if OpenVPN3._status_is_failed(status):
            logger.warning(f'VPN session failed: {status}')
            self._apply_disconnected_state(notify=True)
            return

        logger.warning(f'VPN session inactive: {status}')
        self._apply_disconnected_state(notify=True)

    def _on_config_lookup(self, snapshot: SessionSnapshot):
        if self._shutting_down or self._busy:
            return

        if snapshot.session is None:
            if self.session_path is not None:
                self._apply_disconnected_state()
            return

        if snapshot.connected:
            if self.session_path != snapshot.session.path:
                self._apply_connected_state(snapshot.session.path)
            self._last_snapshot = snapshot
            self._session_poll_timer.start()
            return

        if snapshot.pending_auth:
            self._set_busy(True)
            self._connecting = True
            self._session_poll_timer.start()
            QMetaObject.invokeMethod(
                self._worker,
                'resume_vpn',
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, snapshot.session.path),
            )

    def _set_ui_state(self, state: VpnUiState, hint: str | None = None):
        self._ui_state = state
        title, default_hint = self._STATUS_LABELS[state]
        self.ui.lbl_status.setText(title)
        if hint is None and state == VpnUiState.connected:
            hint = self._build_connected_hint()
        self.ui.lbl_status_hint.setText(hint or default_hint)
        color = STATUS_COLORS[state.value]
        self.ui.lbl_status_dot.setStyleSheet(f"background-color: {color}; {STATUS_DOT_STYLE}")
        self.ui.btn_connect.setStyleSheet(connect_button_style(state))

        if state == VpnUiState.connected:
            self.ui.btn_connect.setText(ConnectButtonText.disconnect.value)
        elif state in (VpnUiState.connecting, VpnUiState.authenticating):
            self.ui.btn_connect.setText(ConnectButtonText.cancel.value)
        elif state == VpnUiState.disconnecting:
            self.ui.btn_connect.setEnabled(False)
        else:
            self.ui.btn_connect.setText(ConnectButtonText.connect.value)

    def _apply_connected_state(self, session_path: str):
        self.session_path = session_path
        self._connecting = False
        self.ui.toolbtn_manage.setDisabled(True)
        self._update_profile_display()
        self._set_ui_state(VpnUiState.connected)
        self._update_controls()

    def _apply_disconnected_state(self, notify: bool = False):
        self.session_path = None
        self._connecting = False
        self._session_poll_timer.stop()
        self.ui.toolbtn_manage.setEnabled(True)
        self._update_profile_display()
        self._set_ui_state(VpnUiState.disconnected)
        self._update_controls()
        if notify:
            self._show_error('VPN disconnected', 'VPN connection was lost.')

    def _update_profile_display(self):
        locked = self.session_path is not None or self._busy
        if locked and self.current_connection:
            name = self.current_connection.get('name', '')
            self.ui.cbox_connections.hide()
            self.ui.lbl_profile_active.setText(name)
            self.ui.lbl_profile_active.show()
        else:
            self.ui.lbl_profile_active.hide()
            self.ui.cbox_connections.show()

    def _build_connected_hint(self) -> str:
        if self._last_snapshot and self._last_snapshot.session and self._last_snapshot.session.status:
            return self._last_snapshot.session.status
        return self._STATUS_LABELS[VpnUiState.connected][1]

    def _refresh_connected_hint(self):
        if self._ui_state == VpnUiState.connected:
            self.ui.lbl_status_hint.setText(self._build_connected_hint())

    def _sync_existing_session(self):
        if self._busy or self.current_connection is None:
            return

        config_filepath = self.current_connection.get('file', '')
        if not config_filepath:
            return

        QMetaObject.invokeMethod(
            self._session_monitor,
            'lookup_config',
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, config_filepath),
        )

    def _cleanup_session_async(self, session_path: str):
        threading.Thread(
            target=OpenVPN3.disconnect,
            args=(session_path,),
            daemon=True,
        ).start()

    def _set_busy(self, busy: bool):
        self._busy = busy
        self._update_controls()

    def _update_controls(self):
        has_connection = bool(self.current_connection) or bool(self.ui.cbox_connections.currentText())
        if self._connecting and self._busy:
            self.ui.btn_connect.setEnabled(True)
        else:
            self.ui.btn_connect.setEnabled(has_connection and not self._busy)
        self.ui.toolbtn_manage.setEnabled(not self._busy and self.session_path is None)

    def _show_error(self, title: str, message: str):
        QMessageBox.warning(self, title, message)

    def update_cbox_connections(self):
        self.ui.cbox_connections.clear()
        self.ui.cbox_connections.addItems([connection.get('name', '#ERROR') for connection in self.connections])
        self._update_profile_display()
        self._update_controls()

    def closeEvent(self, event: QCloseEvent):
        event.accept()
        self._shutdown()

    def _shutdown(self):
        if self._shutting_down:
            return
        self._shutting_down = True

        self._session_poll_timer.stop()
        OpenVPN3.request_shutdown()
        QMetaObject.invokeMethod(
            self._worker,
            'cancel_connect',
            Qt.ConnectionType.QueuedConnection,
        )

        session_path = self.session_path
        if session_path is not None:
            self._cleanup_session_async(session_path)

        self._monitor_thread.quit()
        self._worker_thread.quit()
