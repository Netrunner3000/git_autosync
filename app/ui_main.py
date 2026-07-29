"""Main window for the git_autosync GUI."""
import re
import subprocess
from datetime import datetime, timedelta

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import config, paths, repo_state, scheduler
from .create_repo_dialog import CreateRepoDialog
from .documentation_dialog import DocumentationDialog
from .repo_row import RepoRow
from .runner import AutosyncRunner
from .schedule_dialog import ScheduleDialog

STATUS_BADGE = {
    "SYNCED": "✅ Synced",
    "BLOCKED": "⛔ Blocked",
    "SKIP": "⏭ Skipped",
    "ERROR": "⚠️ Error",
    "OK": "➖ No-op (dry-run)",
}

TRAY_COLORS = {
    "ok": QColor("#2e7d32"),
    "attention": QColor("#c62828"),
    None: QColor("#9e9e9e"),
}

TOOLTIPS = {
    "dry_run_btn": "Scan and report what would happen — never commits or pushes anything.",
    "sync_btn": "Commit and push every clean repo in the list. Disabled until gitleaks is installed.",
    "edit_btn": "Open autosync_repos.txt (one repo per line) in your default editor.",
    "create_repo_btn": "Create a new GitHub repo for a local project (scanned for secrets first).",
    "open_logs_btn": "Reveal the folder with today's and past run logs.",
    "tooltips_btn": "Toggle these explanatory tooltips on the controls below.",
    "docs_btn": "Open the project README for full usage docs.",
    "schedule_btn": "Configure a background schedule for autosync, so it keeps running even when this app is closed.",
    "repo_list": "Repos from autosync_repos.txt. Status badges appear here after a run.",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("git_autosync")
        self.resize(760, 600)

        self.config_path = paths.user_config_path()
        self.runner = AutosyncRunner(self)
        self.runner.output_received.connect(self._append_output)
        self.runner.finished.connect(self._on_finished)

        self._current_dry_run = True
        self._current_single_repo = None
        self._row_widgets: dict[str, RepoRow] = {}
        self._last_findings: dict[str, dict] = {}
        self._tray_hint_shown = False

        self._build_ui()
        self._reload_repo_list()
        self._check_gitleaks()
        self._apply_tooltips(False)
        self._refresh_last_sync_label()
        self._setup_tray()

    # ----- UI construction --------------------------------------------
    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.gitleaks_banner = QLabel()
        self.gitleaks_banner.setWordWrap(True)
        self.gitleaks_banner.setStyleSheet(
            "background:#fff3cd; color:#664d03; padding:8px; border-radius:6px;"
        )
        self.gitleaks_banner.hide()
        layout.addWidget(self.gitleaks_banner)

        repos_label = QLabel("Repos (from autosync_repos.txt)")
        repos_label.setObjectName("sectionLabel")
        layout.addWidget(repos_label)

        self.repo_list = QListWidget()
        self.repo_list.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.repo_list, stretch=1)

        buttons = QHBoxLayout()
        self.dry_run_btn = QPushButton("Dry-run (safe)")
        self.dry_run_btn.clicked.connect(self._on_dry_run)
        self.sync_btn = QPushButton("Sync now")
        self.sync_btn.setObjectName("primaryButton")
        self.sync_btn.clicked.connect(self._on_sync)
        self.edit_btn = QPushButton("Edit repo list")
        self.edit_btn.clicked.connect(self._on_edit_repo_list)
        self.create_repo_btn = QPushButton("Create GitHub repo...")
        self.create_repo_btn.clicked.connect(self._on_create_repo)
        self.open_logs_btn = QPushButton("Open logs")
        self.open_logs_btn.clicked.connect(self._on_open_logs)
        for b in (self.dry_run_btn, self.sync_btn, self.edit_btn, self.create_repo_btn, self.open_logs_btn):
            buttons.addWidget(b)
        layout.addLayout(buttons)

        extras = QHBoxLayout()
        self.tooltips_btn = QPushButton("Tooltips: off")
        self.tooltips_btn.setCheckable(True)
        self.tooltips_btn.toggled.connect(self._on_toggle_tooltips)
        self.docs_btn = QPushButton("Documentation")
        self.docs_btn.clicked.connect(self._on_open_documentation)
        self.schedule_btn = QPushButton("Schedule sync...")
        self.schedule_btn.clicked.connect(self._on_open_schedule_dialog)
        extras.addWidget(self.tooltips_btn)
        extras.addWidget(self.docs_btn)
        extras.addWidget(self.schedule_btn)
        extras.addStretch(1)
        layout.addLayout(extras)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        output_label = QLabel("Output")
        output_label.setObjectName("sectionLabel")
        layout.addWidget(output_label)

        self.output_pane = QPlainTextEdit()
        self.output_pane.setReadOnly(True)
        self.output_pane.setMaximumBlockCount(5000)
        layout.addWidget(self.output_pane, stretch=2)

        self.last_sync_label = QLabel("")
        self.statusBar().addPermanentWidget(self.last_sync_label)
        self.next_sync_label = QLabel("")
        self.statusBar().addPermanentWidget(self.next_sync_label)

    def _refresh_last_sync_label(self):
        stamp = paths.read_last_sync()
        self.last_sync_label.setText(f"Last sync: {stamp}" if stamp else "Last sync: never")
        self._refresh_next_sync_label()

    def _refresh_next_sync_label(self):
        schedule = scheduler.get_schedule()
        if not schedule:
            self.next_sync_label.setText("   Next sync: not scheduled")
            return

        now = datetime.now()
        if schedule["mode"] == "interval":
            stamp = paths.read_last_sync()
            try:
                base = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S") if stamp else now
            except ValueError:
                base = now
            next_run = base + timedelta(seconds=schedule["interval_seconds"])
            if next_run < now:
                next_run = now
        else:
            next_run = now.replace(hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)

        self.next_sync_label.setText(f"   Next sync: ~{next_run.strftime('%Y-%m-%d %H:%M:%S')}")

    # ----- repo list -----------------------------------------------------
    def _reload_repo_list(self):
        self.repo_list.clear()
        self._row_widgets = {}
        no_remote = {p.name for p in paths.repos_without_remote()}
        for name in config.read_repos(self.config_path):
            publish_cb = self._on_publish_single if name in no_remote else None
            row = RepoRow(name, self._on_dry_run_single, self._on_sync_single,
                          on_publish=publish_cb)
            row.label.setText(self._repo_label_text(name, None))
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            item.setData(Qt.UserRole, name)
            self.repo_list.addItem(item)
            self.repo_list.setItemWidget(item, row)
            self._row_widgets[name] = row
        self._apply_tooltips(self.tooltips_btn.isChecked())

    def _repo_label_text(self, name: str, info: dict | None) -> str:
        if info:
            badge = STATUS_BADGE.get(info["status"], info["status"])
            detail = info.get("detail", "")
            finding = self._last_findings.get(name)
            if info["status"] == "BLOCKED" and finding:
                where = f"{finding['file']} ({finding['rule']})" if finding["rule"] else finding["file"]
                detail = f"{detail} — {where}" if detail else where
            text = f"{badge}  {name}"
            if detail:
                text += f"  ({detail})"
            just_synced = info["status"] == "SYNCED"
        else:
            text = name
            just_synced = False

        if not just_synced and repo_state.is_stale(name):
            days = repo_state.days_since_synced(name)
            stale_text = "never synced" if days is None else f"{days}d since last sync"
            text += f"   🕒 {stale_text}"
        return text

    def _set_all_row_buttons_enabled(self, enabled: bool):
        for row in self._row_widgets.values():
            row.set_buttons_enabled(enabled)

    def _check_gitleaks(self):
        found = paths.find_gitleaks()
        self.gitleaks_cmd = found or "gitleaks"
        if not found:
            self.gitleaks_banner.setText(
                "gitleaks not found. Real sync is disabled until it's installed.\n"
                "Install with:  brew install gitleaks"
            )
            self.gitleaks_banner.show()
            self.sync_btn.setEnabled(False)
        else:
            self.gitleaks_banner.hide()
            self.sync_btn.setEnabled(True)

    # ----- actions -------------------------------------------------------
    def _on_dry_run(self):
        self._run(dry_run=True)

    def _on_sync(self):
        if not paths.find_gitleaks():
            QMessageBox.warning(
                self, "gitleaks missing", "Install gitleaks before running a real sync."
            )
            return
        reply = QMessageBox.question(
            self,
            "Confirm sync",
            "This will commit and push changes to GitHub for the listed repos "
            "(after the leak-gate clears each one). Continue?",
        )
        if reply == QMessageBox.Yes:
            self._run(dry_run=False)

    def _on_dry_run_single(self, name: str):
        self._run(dry_run=True, repo=name)

    def _on_sync_single(self, name: str):
        if not paths.find_gitleaks():
            QMessageBox.warning(
                self, "gitleaks missing", "Install gitleaks before running a real sync."
            )
            return
        reply = QMessageBox.question(
            self,
            "Confirm sync",
            f"This will commit and push changes to GitHub for '{name}' "
            "(after the leak-gate clears it). Continue?",
        )
        if reply == QMessageBox.Yes:
            self._run(dry_run=False, repo=name)

    def _run(self, *, dry_run: bool, repo: str | None = None):
        if self.runner.is_running():
            return
        self._current_dry_run = dry_run
        self._current_single_repo = repo
        self.output_pane.clear()
        self.summary_label.setText("Running...")
        self.dry_run_btn.setEnabled(False)
        self.sync_btn.setEnabled(False)
        self._set_all_row_buttons_enabled(False)
        self.runner.start(
            dry_run=dry_run,
            repo=repo,
            config_path=self.config_path,
            gitleaks_cmd=self.gitleaks_cmd,
        )

    def _append_output(self, text: str):
        self.output_pane.appendPlainText(_ANSI_RE.sub("", text).rstrip("\n"))

    def _on_finished(self, exit_code: int, summary: dict):
        self.dry_run_btn.setEnabled(True)
        self._check_gitleaks()  # re-enables sync_btn only if gitleaks present
        self._set_all_row_buttons_enabled(True)

        if not self._current_dry_run:
            self._refresh_last_sync_label()
            synced_now = [n for n, info in summary["repos"].items() if info["status"] == "SYNCED"]
            repo_state.record_synced(synced_now)

        self._last_findings = summary.get("findings", {})
        for name, row in self._row_widgets.items():
            info = summary["repos"].get(name)
            row.label.setText(self._repo_label_text(name, info))

        counts = summary["counts"]
        if counts:
            text = (
                f"synced={counts['synced']} blocked={counts['blocked']} "
                f"skipped={counts['skipped']} errors={counts['errors']} "
                f"noop={counts['noop']}"
            )
        else:
            text = "Run finished (no summary parsed — see output)."

        # Append a plain-English leak summary for any blocked repos.
        blocked_findings = {
            name: f for name, f in self._last_findings.items()
            if summary["repos"].get(name, {}).get("status") == "BLOCKED"
        }
        if blocked_findings:
            lines = ["", "── Leak report ─────────────────────────"]
            for name, finding in blocked_findings.items():
                lines.append(f"⛔ BLOCKED: {name}")
                if finding.get("file"):
                    rule = f"  (rule: {finding['rule']})" if finding.get("rule") else ""
                    lines.append(f"   File:  {finding['file']}{rule}")
            lines.append("─────────────────────────────────────────")
            self.output_pane.appendPlainText("\n".join(lines))

        if exit_code != 0:
            self.summary_label.setStyleSheet(
                "background:#f8d7da; color:#842029; padding:6px; border-radius:6px;"
            )
            text = "Some repos were blocked or errored — see log.  " + text
        else:
            self.summary_label.setStyleSheet(
                "background:#d1e7dd; color:#0f5132; padding:6px; border-radius:6px;"
            )
        self.summary_label.setText(text)
        self._refresh_tray_icon()

    def _on_edit_repo_list(self):
        subprocess.run(["open", "-e", str(self.config_path)])

    def _on_create_repo(self):
        dialog = CreateRepoDialog(self, self.config_path, self.gitleaks_cmd)
        dialog.exec()
        self._reload_repo_list()
        self._refresh_last_sync_label()

    def _on_publish_single(self, name: str):
        dialog = CreateRepoDialog(self, self.config_path, self.gitleaks_cmd,
                                  preselect=name)
        dialog.exec()
        self._reload_repo_list()
        self._refresh_last_sync_label()

    def _on_open_logs(self):
        subprocess.run(["open", str(paths.user_log_dir())])

    def _on_toggle_tooltips(self, enabled: bool):
        self.tooltips_btn.setText(f"Tooltips: {'on' if enabled else 'off'}")
        self._apply_tooltips(enabled)

    def _apply_tooltips(self, enabled: bool):
        widgets = {
            "dry_run_btn": self.dry_run_btn,
            "sync_btn": self.sync_btn,
            "edit_btn": self.edit_btn,
            "create_repo_btn": self.create_repo_btn,
            "open_logs_btn": self.open_logs_btn,
            "tooltips_btn": self.tooltips_btn,
            "docs_btn": self.docs_btn,
            "schedule_btn": self.schedule_btn,
            "repo_list": self.repo_list,
        }
        for key, widget in widgets.items():
            widget.setToolTip(TOOLTIPS[key] if enabled else "")
        for row in self._row_widgets.values():
            row.set_tooltips(enabled)

    def _on_open_schedule_dialog(self):
        dialog = ScheduleDialog(self, self.config_path)
        dialog.exec()
        self._refresh_next_sync_label()

    def _on_open_documentation(self):
        readme = paths.readme_path()
        if readme.exists():
            dialog = DocumentationDialog(self, readme.read_text())
            dialog.exec()
        else:
            QMessageBox.information(
                self,
                "Documentation",
                "README.md wasn't found alongside the app.\n\n"
                "git_autosync scans every repo in autosync_repos.txt with gitleaks "
                "before committing or pushing — a clean scan is required, or the "
                "repo is blocked.",
            )

    # ----- system tray -----------------------------------------------------
    def _setup_tray(self):
        self._tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self._status_icon(paths.read_last_status()))
        self._tray.setToolTip("git_autosync")

        menu = QMenu()
        menu.addAction("Open git_autosync", self._tray_open)
        menu.addSeparator()
        menu.addAction("Dry-run", lambda: self._run(dry_run=True))
        menu.addAction("Sync now", self._on_sync)
        menu.addSeparator()
        menu.addAction("Quit", self._tray_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        # Closing the window keeps the app (and tray icon) alive so it can
        # keep reflecting the background schedule's status.
        QApplication.instance().setQuitOnLastWindowClosed(False)

        self._tray_timer = QTimer(self)
        self._tray_timer.timeout.connect(self._on_tray_tick)
        self._tray_timer.start(60_000)

    def _status_icon(self, status: str | None) -> QIcon:
        color = TRAY_COLORS.get(status, TRAY_COLORS[None])
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        return QIcon(pixmap)

    def _refresh_tray_icon(self):
        if not self._tray:
            return
        status = paths.read_last_status()
        self._tray.setIcon(self._status_icon(status))
        stamp = paths.read_last_sync()
        label = {"ok": "all clear", "attention": "needs attention"}.get(status, "no runs yet")
        self._tray.setToolTip(f"git_autosync — {label}" + (f"\nLast sync: {stamp}" if stamp else ""))

    def _on_tray_tick(self):
        self._refresh_tray_icon()
        self._refresh_last_sync_label()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._tray_open()

    def _tray_open(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.repaint()

    def _tray_quit(self):
        if self._tray:
            self._tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self._tray and self._tray.isVisible():
            event.accept()
            # Step down from foreground so macOS restores focus to the previous
            # app and trackpad gestures work normally. NSApp.hide_ is ⌘H
            # programmatically — no permission prompt, no explicit activation.
            try:
                from AppKit import NSApplication
                NSApplication.sharedApplication().hide_(None)
            except Exception:
                pass
            if not self._tray_hint_shown:
                self._tray.showMessage(
                    "git_autosync",
                    "Still running in the background — click the tray icon to "
                    "reopen, or choose Quit from its menu to stop it.",
                    QSystemTrayIcon.Information,
                    4000,
                )
                self._tray_hint_shown = True
        else:
            event.accept()
