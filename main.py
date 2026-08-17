import sys

from PyQt6.QtWidgets import QApplication

from ui.styles import APP_STYLESHEET
from widgets.mainwindow import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
