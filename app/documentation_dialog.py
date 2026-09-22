"""In-app viewer for README.md — keeps documentation inside the app instead
of shelling out to whatever's registered as the default .md handler
(Pages, VS Code, etc.), which is jarring and inconsistent across machines."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout,
)


class DocumentationDialog(QDialog):
    def __init__(self, parent, markdown_text: str, updated: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Documentation")
        self.resize(700, 700)

        layout = QVBoxLayout(self)

        # Docs age badly and silently. Say when this text last changed so a
        # stale page is obvious rather than trusted.
        self.updated_label = QLabel(
            f"Last updated: {updated}" if updated else "Last updated: unknown")
        self.updated_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.updated_label.setStyleSheet(
            "color:#6E6E73; font-size:11px; padding:2px 4px 6px 0;")
        layout.addWidget(self.updated_label)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(markdown_text)
        # Force readable light palette regardless of app stylesheet
        browser.setStyleSheet(
            "QTextBrowser {"
            "  background: #FFFFFF;"
            "  color: #1D1D1F;"
            "  font-size: 13px;"
            "  padding: 12px;"
            "}"
        )
        layout.addWidget(browser, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Close).clicked.connect(self.reject)
        layout.addWidget(buttons)
