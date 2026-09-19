"""The list header must not clip its own labels.

'LAST SYNCED' needed 83px in a 72px column and rendered as 'AST SYNCED'.
Column widths are constants, so a font or wording change can silently
re-break this; measure it instead of eyeballing a screenshot.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def window():
    from app.ui_main import MainWindow
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    win = MainWindow()
    win.show()
    for _ in range(4):
        app.processEvents()
    yield win
    win._tray = None
    win.close()


def test_header_labels_are_not_clipped(window):
    clipped = []
    for label in window._list_header.findChildren(QtWidgets.QLabel):
        needed = label.fontMetrics().horizontalAdvance(label.text().upper())
        if label.width() and needed > label.width():
            clipped.append((label.text(), label.width(), needed))
    assert not clipped, f"header labels clipped: {clipped}"
