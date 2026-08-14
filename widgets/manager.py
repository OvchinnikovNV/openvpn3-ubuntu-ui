import time

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHeaderView,
    QStyledItemDelegate,
    QTableWidgetItem,
    QWidget,
)

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

        self.connections = connections
        self.emitter = ManagerEmitter()
        self.update_table()
        self.connect_slots()

    def connect_slots(self):
        self.ui.btn_new.clicked.connect(self.on_btn_new)
        self.ui.btn_delete.clicked.connect(self.on_btn_delete)
        self.ui.table.cellChanged.connect(self.on_table_item_changed)
        self.ui.table.cellDoubleClicked.connect(self.on_table_item_double_clicked)

    def update_table(self):
        self.ui.table.setRowCount(0)
        for row, connection in enumerate(self.connections):
            self._insert_row(row, connection.get('name', '#ERROR'), connection.get('file', '#ERROR'))

    def _insert_row(self, row: int, name: str, file: str):
        self.ui.table.insertRow(row)
        self.ui.table.setItem(row, 0, QTableWidgetItem(name))
        self.ui.table.setItem(row, 1, QTableWidgetItem(file))

    def _pick_config_file(self) -> str:
        file_path, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption='Choose connection file',
            filter='Configurations (*.ovpn)',
        )
        return file_path

    def on_btn_new(self):
        file_path = self._pick_config_file()
        if not file_path:
            return

        connection_name = f'Connection-{int(time.time())}'
        self.connections.append({'name': connection_name, 'file': file_path})
        ConnectionsFile.write(self.connections)
        self._insert_row(self.ui.table.rowCount(), connection_name, file_path)
        self.emitter.connections_changed.emit(self.connections)

    def on_btn_delete(self):
        selected = self.ui.table.selectedItems()
        if not selected:
            return

        try:
            row = selected[0].row()
            self.ui.table.removeRow(row)
            self.connections.pop(row)
            ConnectionsFile.write(self.connections)
            self.emitter.connections_changed.emit(self.connections)
        except Exception as e:
            logger.exception(e)

    def on_table_item_changed(self, row: int, col: int):
        if col > 0:
            return

        item = self.ui.table.item(row, col)
        if item is None:
            return

        self.connections[row]['name'] = item.text()
        ConnectionsFile.write(self.connections)
        self.emitter.connections_changed.emit(self.connections)

    def on_table_item_double_clicked(self, row: int, col: int):
        if col != 1:
            return

        file_path = self._pick_config_file()
        if not file_path:
            return

        self.ui.table.setItem(row, col, QTableWidgetItem(file_path))
        self.connections[row]['file'] = file_path
        ConnectionsFile.write(self.connections)
        self.emitter.connections_changed.emit(self.connections)
