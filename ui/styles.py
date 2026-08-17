from utils.enums import VpnUiState

APP_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #1a1f2e;
    color: #e2e8f0;
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 13px;
}

QWidget#centralwidget {
    background-color: #1a1f2e;
}

QFrame#status_card {
    background-color: #252b3b;
    border: 1px solid #334155;
    border-radius: 14px;
}

QLabel#lbl_title {
    font-size: 20px;
    font-weight: 700;
    color: #f1f5f9;
}

QLabel#lbl_subtitle {
    font-size: 12px;
    color: #94a3b8;
}

QLabel#lbl_section {
    font-size: 11px;
    font-weight: 600;
    color: #94a3b8;
}

QLabel#lbl_status {
    font-size: 15px;
    font-weight: 600;
    color: #f1f5f9;
}

QLabel#lbl_status_hint {
    font-size: 12px;
    color: #94a3b8;
}

QComboBox {
    background-color: #252b3b;
    color: #e2e8f0;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 20px;
}

QComboBox:hover {
    border-color: #64748b;
}

QComboBox:focus {
    border-color: #4285f4;
}

QComboBox:disabled {
    background-color: #1e2535;
    color: #cbd5e1;
    border-color: #334155;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #94a3b8;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #252b3b;
    color: #e2e8f0;
    border: 1px solid #475569;
    border-radius: 8px;
    selection-background-color: #334155;
    selection-color: #f1f5f9;
    padding: 4px;
    outline: none;
}

QLabel#lbl_profile_active {
    background-color: #1e2535;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 500;
}

QToolButton#toolbtn_manage {
    background-color: #252b3b;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
    color: #cbd5e1;
}

QToolButton#toolbtn_manage:hover {
    background-color: #334155;
    border-color: #64748b;
    color: #f1f5f9;
}

QToolButton#toolbtn_manage:disabled {
    background-color: #1e2535;
    color: #64748b;
    border-color: #334155;
}

QTableWidget {
    background-color: #252b3b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 10px;
    gridline-color: #334155;
}

QTableWidget::item {
    padding: 6px;
    color: #e2e8f0;
}

QTableWidget::item:selected {
    background-color: #334155;
    color: #f1f5f9;
}

QHeaderView::section {
    background-color: #1e2535;
    border: none;
    border-bottom: 1px solid #334155;
    padding: 8px;
    font-weight: 600;
    color: #94a3b8;
}

QPushButton {
    background-color: #252b3b;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 8px 16px;
    color: #e2e8f0;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #64748b;
}

QPushButton#btn_new {
    background-color: #4285f4;
    border: none;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#btn_new:hover {
    background-color: #3367d6;
}

QPushButton#btn_delete {
    color: #f87171;
}

QPushButton#btn_delete:hover {
    background-color: #3b2020;
    border-color: #7f1d1d;
}

QMessageBox {
    background-color: #252b3b;
    color: #e2e8f0;
}

QMessageBox QLabel {
    color: #e2e8f0;
}
"""

_BTN_ROUND = """
    padding: 0px;
    margin: 0px;
    border: none;
    outline: none;
    border-radius: 60px;
    min-width: 120px;
    max-width: 120px;
    min-height: 120px;
    max-height: 120px;
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
"""

BTN_STYLE_CONNECT = f"""
QPushButton#btn_connect {{
{_BTN_ROUND}
    background-color: #4285f4;
}}
QPushButton#btn_connect:hover {{
    background-color: #3367d6;
}}
QPushButton#btn_connect:pressed {{
    background-color: #2a56c6;
}}
"""

BTN_STYLE_DISCONNECT = f"""
QPushButton#btn_connect {{
{_BTN_ROUND}
    background-color: #475569;
}}
QPushButton#btn_connect:hover {{
    background-color: #64748b;
}}
QPushButton#btn_connect:pressed {{
    background-color: #334155;
}}
"""

BTN_STYLE_CONNECTING = f"""
QPushButton#btn_connect {{
{_BTN_ROUND}
    background-color: #d97706;
}}
QPushButton#btn_connect:hover {{
    background-color: #b45309;
}}
QPushButton#btn_connect:pressed {{
    background-color: #92400e;
}}
"""

STATUS_DOT_STYLE = "border-radius: 7px; min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px;"

STATUS_COLORS = {
    "disconnected": "#64748b",
    "connecting": "#f59e0b",
    "authenticating": "#a78bfa",
    "connected": "#22c55e",
    "disconnecting": "#f59e0b",
}


def connect_button_style(state: VpnUiState) -> str:
    if state == VpnUiState.connected:
        return BTN_STYLE_DISCONNECT
    if state in (VpnUiState.connecting, VpnUiState.authenticating, VpnUiState.disconnecting):
        return BTN_STYLE_CONNECTING
    return BTN_STYLE_CONNECT
