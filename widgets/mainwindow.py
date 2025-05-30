import sys

from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QMainWindow

from ui.pyuic.mainwindow import Ui_MainWindow
from utils.connections_file import ConnectionsFile
from utils.openvpn3 import OpenVPN3
from widgets.manager import Manager
from logger import logger
from utils.enums import ConnectButtonText


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.btn_connect.setText(ConnectButtonText.connect.value)
        self.ui.btn_connect.setFixedSize(120, 120)

        """ Current connection from ComboBox """
        self.current_connection: dict[str, str] | None = None

        """ Connected session path """
        self.session_path: str | None = None

        """ Get connections from json """
        self.connections = ConnectionsFile.get()

        """ Connect signals """
        self.connect_slots()

        """ Update ComboBox """
        self.update_cbox_connections()

    def connect_slots(self):
        self.ui.toolbtn_manage.clicked.connect(self.on_toolbtn_manage)
        self.ui.cbox_connections.currentIndexChanged.connect(self.on_cbox_connections_index_changed)
        self.ui.btn_connect.clicked.connect(self.on_btn_connect)

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
            return

        try:
            self.current_connection = self.connections[i]
        except Exception as e:
            logger.exception(e)
            sys.exit(1)

    def on_btn_connect(self):
        btn_connect_text = self.ui.btn_connect.text()

        if btn_connect_text == ConnectButtonText.connect.value:
            config_filepath = self.current_connection.get('file', '')
            if not config_filepath:
                return

            session_path: str | None = OpenVPN3.start_session(config_filepath)
            if session_path is None:
                return

            logger.success(f"Connected to {self.current_connection.get('name', '#UNKNOWN')}!")

            self.session_path = session_path
            self.ui.cbox_connections.setDisabled(True)
            self.ui.toolbtn_manage.setDisabled(True)
            self.ui.btn_connect.setText(ConnectButtonText.disconnect.value)

        elif btn_connect_text == ConnectButtonText.disconnect.value:
            disconnected = OpenVPN3.disconnect(self.session_path)
            if not disconnected:
                return

            logger.success(f"Disconnected from {self.current_connection.get('name', '#UNKNOWN')}!")

            self.session_path = None
            self.ui.cbox_connections.setEnabled(True)
            self.ui.toolbtn_manage.setEnabled(True)
            self.ui.btn_connect.setText(ConnectButtonText.connect.value)

    def update_cbox_connections(self):
        self.ui.cbox_connections.clear()
        self.ui.cbox_connections.addItems([connection.get('name', '#ERROR') for connection in self.connections])
        self.ui.btn_connect.setEnabled(bool(self.ui.cbox_connections.currentText()))

    def closeEvent(self, a0: QCloseEvent):
        if self.session_path is not None:
            self.on_btn_connect()
        super().closeEvent(a0)
