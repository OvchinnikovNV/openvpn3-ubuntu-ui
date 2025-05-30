import sys
import time
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtWidgets import QDialog, QWidget, QFileDialog, QTableWidgetItem, QStyledItemDelegate, QHeaderView

from logger import logger
from ui.pyuic.manager import Ui_Manager
from utils.connections_file import ConnectionsFile


class NonEditableDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return None


class ManagerEmitter(QObject):
    connections_changed = pyqtSignal(object)


class Manager(QDialog):
    def __init__(self, connections: list[dict], parent: QWidget | None = None):
        super().__init__(parent)
        self.ui = Ui_Manager()
        self.ui.setupUi(self)
        self.ui.table.setItemDelegateForColumn(1, NonEditableDelegate(self.ui.table))
        self.ui.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        """ Get connections and update table """
        self.connections: list[dict] = connections
        self.update_table()

        """ Init emitter and connect signals """
        self.emitter = ManagerEmitter()
        self.connect_slots()

    def connect_slots(self):
        self.ui.btn_new.clicked.connect(self.on_btn_new)
        self.ui.btn_delete.clicked.connect(self.on_btn_delete)
        self.ui.table.cellChanged.connect(self.on_table_item_changed)
        self.ui.table.cellDoubleClicked.connect(self.on_table_item_double_clicked)

    def update_table(self):
        self.ui.table.clearContents()
        for row, connection in enumerate(self.connections):
            self.insert_connection_row(row, connection.get('name', '#ERROR'), connection.get('file', '#ERROR'))

    def insert_connection_row(self, row: int, name: str, file: str):
        self.ui.table.insertRow(row)
        self.ui.table.setItem(row, 0, QTableWidgetItem(name))
        self.ui.table.setItem(row, 1, QTableWidgetItem(file))

    def fill_connections_table(self, connections: list[dict]):
        try:
            for i, connection in enumerate(connections):
                self.insert_connection_row(i, connection["name"], connection["file"])
        except Exception as e:
            logger.exception(e)
            sys.exit(1)

    def get_openvpn_filename(self) -> str:
        file_path, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="Choose connection file",
            directory="",
            filter="Configurations (*.ovpn)",
        )
        return file_path

    def on_btn_new(self):
        file_path = self.get_openvpn_filename()
        if not file_path:
            return

        connection_name = f"Connection-{int(time.time())}"
        self.connections.append({
            "name": connection_name,
            "file": file_path,
        })
        ConnectionsFile.write(self.connections)
        self.insert_connection_row(self.ui.table.rowCount(), connection_name, file_path)
        self.emitter.connections_changed.emit(self.connections)

    def on_btn_delete(self):
        """Возвращает индекс выделенной строки или None"""
        selected = self.ui.table.selectedItems()
        if not selected:
            return None

        try:
            row = selected[0].row()
            self.ui.table.removeRow(row)
            self.connections.pop(row)
            ConnectionsFile.write(self.connections)
            self.emitter.connections_changed.emit(self.connections)
        except Exception as e:
            logger.exception(e)

        return None



    def on_table_item_changed(self, row: int, col: int):
        if col > 0:
            return

        for i, connection in enumerate(self.connections):
            if i == row:
                self.connections[i]['name'] = self.ui.table.item(row, col).text()
                break

        ConnectionsFile.write(self.connections)
        self.emitter.connections_changed.emit(self.connections)

    def on_table_item_double_clicked(self, row: int, col: int):
        if col != 1:
            return

        file_path = self.get_openvpn_filename()
        if not file_path:
            return

        self.ui.table.setItem(row, col, QTableWidgetItem(file_path))
        for i, connection in enumerate(self.connections):
            if i == row:
                self.connections[i]['file'] = file_path
                break

        ConnectionsFile.write(self.connections)
        self.emitter.connections_changed.emit(self.connections)
