"""A single row in the repo list: status label plus per-repo Dry-run/Sync
buttons, so an action can target one repo without running the whole list.
Repos without a GitHub remote get a Publish button instead of Sync."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget


class RepoRow(QWidget):
    def __init__(self, name: str, on_dry_run, on_sync, on_publish=None):
        super().__init__()
        self.name = name
        self._has_remote = on_publish is None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.label = QLabel(name)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.label, stretch=1)

        self.dry_run_btn = QPushButton("Dry-run")
        self.dry_run_btn.setProperty("class", "rowButton")
        self.dry_run_btn.clicked.connect(lambda: on_dry_run(name))
        layout.addWidget(self.dry_run_btn)

        if on_publish is not None:
            self.sync_btn = None
            self.publish_btn = QPushButton("Publish to GitHub…")
            self.publish_btn.setProperty("class", "rowButton")
            self.publish_btn.setToolTip(f"Create a GitHub repo for {name} and push (leak-gated).")
            self.publish_btn.clicked.connect(lambda: on_publish(name))
            layout.addWidget(self.publish_btn)
        else:
            self.publish_btn = None
            self.sync_btn = QPushButton("Sync")
            self.sync_btn.setProperty("class", "rowButton")
            self.sync_btn.clicked.connect(lambda: on_sync(name))
            layout.addWidget(self.sync_btn)

    def set_buttons_enabled(self, enabled: bool):
        self.dry_run_btn.setEnabled(enabled)
        if self.sync_btn:
            self.sync_btn.setEnabled(enabled)
        if self.publish_btn:
            self.publish_btn.setEnabled(enabled)

    def set_tooltips(self, enabled: bool):
        text_dry = f"Dry-run just {self.name}." if enabled else ""
        self.dry_run_btn.setToolTip(text_dry)
        if self.sync_btn:
            self.sync_btn.setToolTip(
                f"Sync just {self.name} (after the leak-gate clears it)." if enabled else ""
            )
        if self.publish_btn:
            self.publish_btn.setToolTip(
                f"Create a GitHub repo for {self.name} and push (leak-gated)." if enabled else ""
            )
