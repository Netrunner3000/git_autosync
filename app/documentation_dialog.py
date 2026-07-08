"""In-app viewer for README.md — keeps documentation inside the app instead
of shelling out to whatever's registered as the default .md handler
(Pages, VS Code, etc.), which is jarring and inconsistent across machines."""
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout


class DocumentationDialog(QDialog):
    def __init__(self, parent, markdown_text: str):
        super().__init__(parent)
        self.setWindowTitle("Documentation")
        self.resize(640, 640)

        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(markdown_text)
        layout.addWidget(browser, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Close).clicked.connect(self.reject)
        layout.addWidget(buttons)
