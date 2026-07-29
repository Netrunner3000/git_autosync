import sys

from PySide6.QtCore import QEvent, QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from .style import STYLESHEET
from .ui_main import MainWindow

_SOCKET_NAME = "git_autosync_instance"


class _DockActivateFilter(QObject):
    """Reopens the window when the macOS Dock icon is clicked while hidden."""

    def __init__(self, window: MainWindow):
        super().__init__()
        self._window = window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.ApplicationActivate and not self._window.isVisible():
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()
            self._window.repaint()
        return False


def main():
    app = QApplication(sys.argv)

    # Try to connect to an already-running instance.
    sock = QLocalSocket()
    sock.connectToServer(_SOCKET_NAME)
    if sock.waitForConnected(300):
        sock.write(b"raise")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        msg = QMessageBox()
        msg.setWindowTitle("git_autosync")
        msg.setText("git_autosync is already running.")
        msg.setInformativeText("The existing window has been brought to the front.")
        msg.setIcon(QMessageBox.Information)
        msg.exec()
        sys.exit(0)

    # Primary instance — claim the socket name and start listening.
    QLocalServer.removeServer(_SOCKET_NAME)
    server = QLocalServer()
    server.listen(_SOCKET_NAME)

    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()

    def _on_new_connection():
        conn = server.nextPendingConnection()
        conn.waitForReadyRead(300)
        window.show()
        window.raise_()
        window.activateWindow()

    server.newConnection.connect(_on_new_connection)

    # Keep filter alive for the lifetime of the app.
    dock_filter = _DockActivateFilter(window)
    app.installEventFilter(dock_filter)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
