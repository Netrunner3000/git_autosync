import sys

from PySide6.QtCore import QEvent, QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from .style import STYLESHEET
from .ui_main import MainWindow

_SOCKET_NAME = "git_autosync_instance"


class _App(QApplication):
    """QApplication subclass that intercepts macOS Cmd+Q / Dock Quit.

    Overriding event() at the QApplication level is the only reliable way
    to catch these on macOS — an event filter on the app object receives
    the Close event before super().event() would call quit().
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.allow_quit = False   # set True by the tray's own Quit action
        self._window: MainWindow | None = None

    def event(self, e):
        # An explicit quit gesture (Cmd+Q, Dock → Quit) arrives as QEvent.Quit
        # and must really terminate. macOS implements it by asking every window
        # to close, so flag it first: MainWindow.closeEvent hides to the tray
        # instead of closing unless this flag says the user asked to quit.
        if e.type() == QEvent.Quit:
            self.allow_quit = True
        return super().event(e)


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
    background = "--background" in sys.argv
    if background:
        sys.argv.remove("--background")
    app = _App(sys.argv)

    # Try to connect to an already-running instance.
    sock = QLocalSocket()
    sock.connectToServer(_SOCKET_NAME)
    if sock.waitForConnected(300):
        sock.write(b"background" if background else b"raise")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        if not background:
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
    app._window = window

    if not background:
        window.show()

    def _on_new_connection():
        conn = server.nextPendingConnection()
        conn.waitForReadyRead(300)
        if bytes(conn.readAll()) == b"background":
            return
        window.show()
        window.raise_()
        window.activateWindow()

    server.newConnection.connect(_on_new_connection)

    dock_filter = _DockActivateFilter(window)
    app.installEventFilter(dock_filter)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
