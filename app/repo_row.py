"""A single row in the repo list: status label plus per-repo Dry-run/Sync
buttons, so an action can target one repo without running the whole list."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget


class RepoRow(QWidget):
    def __init__(self, name: str, on_dry_run, on_sync):
        super().__init__()
        self.name = name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.label = QLabel(name)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.label, stretch=1)

        self.dry_run_btn = QPushButton("Dry-run")
        self.dry_run_btn.setProperty("class", "rowButton")
        self.dry_run_btn.clicked.connect(lambda: on_dry_run(name))
        layout.addWidget(self.dry_run_btn)

        self.sync_btn = QPushButton("Sync")
        self.sync_btn.setProperty("class", "rowButton")
        self.sync_btn.clicked.connect(lambda: on_sync(name))
        layout.addWidget(self.sync_btn)

    def set_buttons_enabled(self, enabled: bool):
        self.dry_run_btn.setEnabled(enabled)
        self.sync_btn.setEnabled(enabled)

    def set_tooltips(self, enabled: bool):
        text_dry = f"Dry-run just {self.name}." if enabled else ""
        text_sync = f"Sync just {self.name} (after the leak-gate clears it)." if enabled else ""
        self.dry_run_btn.setToolTip(text_dry)
        self.sync_btn.setToolTip(text_sync)
