"""A single row in the repo list with checkbox, status badge, time label, and actions."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget,
)

_BADGE = {
    "SYNCED":  ("#D1F2DC", "#1A7A3A", "✓ Synced"),
    "BLOCKED": ("#FFE5E3", "#C0392B", "✕ Blocked"),
    "SKIP":    ("#F0F0F5", "#6E6E73", "⊘ Skipped"),
    "ERROR":   ("#FFF0E0", "#B45309", "⚠ Error"),
    "OK":      ("#F0F0F5", "#6E6E73", "No changes"),
}
_TIME_STYLE  = "color:#6E6E73; font-size:11px;"
_STALE_STYLE = "background:#FFF8E7; color:#92400E; border-radius:5px; padding:2px 7px; font-size:11px; font-weight:600;"
_EMPTY_STYLE = "background:transparent;"


class RepoRow(QWidget):
    def __init__(self, name: str, on_dry_run, on_sync, on_publish=None, on_privacy=None, on_ignore=None):
        super().__init__()
        self.name = name
        self._status = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 10, 6)
        layout.setSpacing(8)

        # Selection checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.setToolTip("Include in bulk Dry-run / Sync now")
        layout.addWidget(self.checkbox)

        self.label = QLabel(name)
        self.label.setObjectName("repoName")
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.label, stretch=1)

        # Last-synced time (subtle, always shown when known)
        self.time_label = QLabel()
        self.time_label.setFixedWidth(72)
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.time_label.setStyleSheet(_EMPTY_STYLE)
        layout.addWidget(self.time_label)

        # Colored status badge — hidden until first run
        self.badge = QLabel()
        self.badge.setFixedWidth(88)
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setStyleSheet(_EMPTY_STYLE)
        layout.addWidget(self.badge)

        self.dry_run_btn = QPushButton("Dry-run")
        self.dry_run_btn.setProperty("class", "rowButton")
        self.dry_run_btn.clicked.connect(lambda: on_dry_run(name))
        layout.addWidget(self.dry_run_btn)

        if on_publish is not None:
            self.sync_btn    = None
            self.privacy_btn = None
            self.publish_btn = QPushButton("Publish to GitHub…")
            self.publish_btn.setProperty("class", "rowButton")
            self.publish_btn.clicked.connect(lambda: on_publish(name))
            layout.addWidget(self.publish_btn)
        else:
            self.publish_btn = None
            self.sync_btn = QPushButton("Sync")
            self.sync_btn.setProperty("class", "rowButton")
            self.sync_btn.clicked.connect(lambda: on_sync(name))
            layout.addWidget(self.sync_btn)

            self.privacy_btn = QPushButton("Privacy…")
            self.privacy_btn.setProperty("class", "rowButton")
            self.privacy_btn.clicked.connect(lambda: on_privacy(name))
            layout.addWidget(self.privacy_btn)

        if on_ignore is not None:
            self.ignore_btn = QPushButton("Ignore…")
            self.ignore_btn.setProperty("class", "rowButton")
            self.ignore_btn.setToolTip("Allowlist the last gitleaks finding for this repo (false positives only).")
            self.ignore_btn.clicked.connect(lambda: on_ignore(name))
            layout.addWidget(self.ignore_btn)
        else:
            self.ignore_btn = None

    # ── public API ────────────────────────────────────────────────

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def set_status(self, status: str | None):
        self._status = status
        if status and status in _BADGE:
            bg, fg, text = _BADGE[status]
            self.badge.setText(text)
            self.badge.setStyleSheet(
                f"background:{bg}; color:{fg}; border-radius:5px;"
                f" padding:2px 7px; font-size:11px; font-weight:600;"
            )
        else:
            self.badge.setText("")
            self.badge.setStyleSheet(_EMPTY_STYLE)

    def set_time(self, time_str: str | None, stale: bool = False):
        """Show last-synced time. Amber pill if stale, subtle grey if recent."""
        if time_str is None:
            self.time_label.setText("never")
            self.time_label.setStyleSheet(_STALE_STYLE)
        elif stale:
            self.time_label.setText(time_str)
            self.time_label.setStyleSheet(_STALE_STYLE)
        else:
            self.time_label.setText(time_str)
            self.time_label.setStyleSheet(_TIME_STYLE)

    def set_stale(self, days: int | None):
        """Legacy shim — callers that pass days still work."""
        if days is None or days < 0:
            self.time_label.setText("")
            self.time_label.setStyleSheet(_EMPTY_STYLE)
        elif days == 0:
            self.set_time("today", stale=False)
        else:
            self.set_time(f"{days}d ago", stale=days >= 3)

    def set_buttons_enabled(self, enabled: bool):
        self.dry_run_btn.setEnabled(enabled)
        if self.sync_btn:    self.sync_btn.setEnabled(enabled)
        if self.publish_btn: self.publish_btn.setEnabled(enabled)
        if self.privacy_btn: self.privacy_btn.setEnabled(enabled)
        if self.ignore_btn:  self.ignore_btn.setEnabled(enabled)

    def set_tooltips(self, enabled: bool):
        self.dry_run_btn.setToolTip(f"Dry-run just {self.name}." if enabled else "")
        if self.sync_btn:
            self.sync_btn.setToolTip(
                f"Sync just {self.name} (leak-gate must clear first)." if enabled else ""
            )
        if self.publish_btn:
            self.publish_btn.setToolTip(
                f"Create a GitHub repo for {self.name} and push (leak-gated)." if enabled else ""
            )
        if self.privacy_btn:
            self.privacy_btn.setToolTip(
                f"Toggle {self.name} between public and private on GitHub." if enabled else ""
            )
