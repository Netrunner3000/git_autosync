"""Main window for the git_autosync GUI."""
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QFileSystemWatcher, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from .ignore_dialog import IgnoreDialog
from .repo_row import RepoRow
from .runner import AutosyncRunner
from .schedule_dialog import ScheduleDialog

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

TRAY_COLORS = {
    "ok":        QColor("#2e7d32"),
    "attention": QColor("#c62828"),
    None:        QColor("#9e9e9e"),
}

TOOLTIPS = {
    "dry_run_btn":    "Scan all repos and show what would happen — never commits or pushes.",
    "sync_btn":       "Commit and push every clean repo. Leak-gate must pass first.",
    "edit_btn":       "Open autosync_repos.txt in your default editor.",
    "create_repo_btn":"Create a new GitHub repo for a local project (scanned for secrets first).",
    "open_logs_btn":  "Reveal the log folder in Finder.",
    "tooltips_btn":   "Toggle explanatory tooltips on all controls.",
    "docs_btn":       "Open the project README inside the app.",
    "schedule_btn":   "Configure a background launchd schedule so syncs run automatically.",
    "msg_field":      "Optional: set a custom commit message instead of the default timestamp one.",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("git_autosync")
        self.setMinimumSize(700, 500)
        self.resize(860, 700)

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
        self._setup_file_watcher()

    # ── UI construction ────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        # gitleaks warning banner
        self.gitleaks_banner = QLabel()
        self.gitleaks_banner.setWordWrap(True)
        self.gitleaks_banner.setStyleSheet(
            "background:#FFF3CD; color:#664D03; padding:10px 12px;"
            " border:1px solid #FFE69C; border-radius:8px;"
        )
        self.gitleaks_banner.hide()
        root.addWidget(self.gitleaks_banner)

        # ── Repos section ──────────────────────────────────────────
        repos_header = QHBoxLayout()
        repos_lbl = QLabel("Repositories")
        repos_lbl.setObjectName("sectionLabel")
        repos_header.addWidget(repos_lbl)
        repos_header.addStretch(1)
        self.select_all_btn = QPushButton("All")
        self.select_all_btn.setProperty("class", "rowButton")
        self.select_all_btn.setFixedWidth(38)
        self.select_all_btn.setToolTip("Select all repos")
        self.select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        self.select_none_btn = QPushButton("None")
        self.select_none_btn.setProperty("class", "rowButton")
        self.select_none_btn.setFixedWidth(44)
        self.select_none_btn.setToolTip("Deselect all repos")
        self.select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        repos_header.addWidget(self.select_all_btn)
        repos_header.addWidget(self.select_none_btn)
        self.edit_btn = QPushButton("Edit list")
        self.edit_btn.clicked.connect(self._on_edit_repo_list)
        repos_header.addWidget(self.edit_btn)
        root.addLayout(repos_header)

        self.repo_list = QListWidget()
        self.repo_list.setSelectionMode(QAbstractItemView.NoSelection)
        root.addWidget(self.repo_list, stretch=1)

        # ── Commit message ─────────────────────────────────────────
        self.msg_field = QLineEdit()
        self.msg_field.setPlaceholderText(
            "Custom commit message (optional) — leave blank for the default timestamp"
        )
        root.addWidget(self.msg_field)

        # ── Primary actions ────────────────────────────────────────
        primary_row = QHBoxLayout()
        primary_row.setSpacing(10)
        self.dry_run_btn = QPushButton("Dry-run (safe)")
        self.dry_run_btn.setObjectName("secondaryButton")
        self.dry_run_btn.clicked.connect(self._on_dry_run)
        self.sync_btn = QPushButton("Sync now")
        self.sync_btn.setObjectName("primaryButton")
        self.sync_btn.clicked.connect(self._on_sync)
        primary_row.addWidget(self.dry_run_btn)
        primary_row.addWidget(self.sync_btn, stretch=1)
        root.addLayout(primary_row)

        # ── Secondary actions ──────────────────────────────────────
        secondary_row = QHBoxLayout()
        secondary_row.setSpacing(8)
        self.create_repo_btn = QPushButton("Create GitHub Repo…")
        self.create_repo_btn.clicked.connect(self._on_create_repo)
        self.schedule_btn = QPushButton("Schedule…")
        self.schedule_btn.clicked.connect(self._on_open_schedule_dialog)
        self.open_logs_btn = QPushButton("Logs")
        self.open_logs_btn.clicked.connect(self._on_open_logs)
        self.docs_btn = QPushButton("Docs")
        self.docs_btn.clicked.connect(self._on_open_documentation)
        self.tooltips_btn = QPushButton("Tooltips")
        self.tooltips_btn.setCheckable(True)
        self.tooltips_btn.toggled.connect(self._on_toggle_tooltips)
        for b in (self.create_repo_btn, self.schedule_btn,
                  self.open_logs_btn, self.docs_btn, self.tooltips_btn):
            secondary_row.addWidget(b)
        secondary_row.addStretch(1)
        root.addLayout(secondary_row)

        # ── Summary banner ─────────────────────────────────────────
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.hide()
        root.addWidget(self.summary_label)

        # ── Output ────────────────────────────────────────────────
        output_lbl = QLabel("Output")
        output_lbl.setObjectName("sectionLabel")
        root.addWidget(output_lbl)

        self.output_pane = QPlainTextEdit()
        self.output_pane.setReadOnly(True)
        self.output_pane.setMaximumBlockCount(5000)
        self.output_pane.setMinimumHeight(120)
        root.addWidget(self.output_pane, stretch=1)

        # ── Status bar ─────────────────────────────────────────────
        self.last_sync_label = QLabel()
        self.statusBar().addPermanentWidget(self.last_sync_label)
        self.next_sync_label = QLabel()
        self.statusBar().addPermanentWidget(self.next_sync_label)

    # ── File watcher (auto-reload repo list) ──────────────────────

    def _setup_file_watcher(self):
        self._watcher = QFileSystemWatcher([str(self.config_path)], self)
        self._watcher.fileChanged.connect(self._on_config_file_changed)

    def _on_config_file_changed(self, _path: str):
        # Re-add path in case editor replaced the file (some editors do)
        self._watcher.addPath(str(self.config_path))
        self._reload_repo_list()

    # ── Sync timestamps ────────────────────────────────────────────

    def _refresh_last_sync_label(self):
        stamp = paths.read_last_sync()
        self.last_sync_label.setText(f"  Last sync: {stamp}" if stamp else "  Last sync: never")
        self._refresh_next_sync_label()

    def _refresh_next_sync_label(self):
        schedule = scheduler.get_schedule()
        if not schedule:
            self.next_sync_label.setText("   Next sync: not scheduled  ")
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
            next_run = now.replace(
                hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0
            )
            if next_run <= now:
                next_run += timedelta(days=1)
        self.next_sync_label.setText(
            f"   Next sync: ~{next_run.strftime('%Y-%m-%d %H:%M')}  "
        )

    # ── Repo list ─────────────────────────────────────────────────

    def _reload_repo_list(self):
        self.repo_list.clear()
        self._row_widgets = {}
        no_remote = {p.name for p in paths.repos_without_remote()}
        for name in config.read_repos(self.config_path):
            publish_cb = self._on_publish_single if name in no_remote else None
            privacy_cb = None if name in no_remote else self._on_privacy_single
            row = RepoRow(name, self._on_dry_run_single, self._on_sync_single,
                          on_publish=publish_cb, on_privacy=privacy_cb)
            time_str = repo_state.time_since_synced(name)
            row.set_time(time_str, stale=repo_state.is_stale(name))
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            item.setData(Qt.UserRole, name)
            self.repo_list.addItem(item)
            self.repo_list.setItemWidget(item, row)
            self._row_widgets[name] = row
        self._apply_tooltips(self.tooltips_btn.isChecked())

    def _set_all_checked(self, checked: bool):
        for row in self._row_widgets.values():
            row.checkbox.setChecked(checked)

    def _checked_repos(self) -> list[str]:
        """Names of repos whose checkbox is ticked. Falls back to all if none ticked."""
        checked = [n for n, r in self._row_widgets.items() if r.is_checked()]
        return checked if checked else list(self._row_widgets.keys())

    def _set_all_row_buttons_enabled(self, enabled: bool):
        for row in self._row_widgets.values():
            row.set_buttons_enabled(enabled)

    def _check_gitleaks(self):
        found = paths.find_gitleaks()
        self.gitleaks_cmd = found or "gitleaks"
        if not found:
            self.gitleaks_banner.setText(
                "gitleaks not found — real syncs are disabled until it's installed.\n"
                "Run:  brew install gitleaks"
            )
            self.gitleaks_banner.show()
            self.sync_btn.setEnabled(False)
        else:
            self.gitleaks_banner.hide()
            self.sync_btn.setEnabled(True)

    # ── Diff preview ──────────────────────────────────────────────

    def _diff_preview(self, repo: str | None = None, repos: list | None = None) -> str:
        """Return a git status --short summary for repos that have changes."""
        git = paths.find_git() or "git"
        lab = paths.lab_active_dir()
        if repo:
            names = [repo]
        elif repos is not None:
            names = repos
        else:
            names = config.read_repos(self.config_path)
        lines = []
        for name in names:
            raw = name
            if raw.startswith("/") or raw.startswith("~"):
                repo_path = Path(raw).expanduser()
            else:
                repo_path = lab / raw
            if not repo_path.is_dir():
                continue
            result = subprocess.run(
                [git, "-C", str(repo_path), "status", "--short"],
                capture_output=True, text=True,
            )
            stat = result.stdout.strip()
            if stat:
                lines.append(f"{name}:\n{stat}")
        return "\n\n".join(lines) if lines else ""

    # ── Actions ───────────────────────────────────────────────────

    def _on_dry_run(self):
        repos = self._checked_repos()
        if len(repos) == len(self._row_widgets):
            self._run(dry_run=True)
        else:
            # Run each checked repo sequentially via a single invocation isn't
            # possible with the current engine (one --repo at a time), so for
            # a subset we just run all and filter visually — or run per-repo.
            # Simplest correct approach: run all but only show status for checked.
            self._run(dry_run=True, repos=repos)

    def _on_sync(self):
        if not paths.find_gitleaks():
            QMessageBox.warning(self, "gitleaks missing",
                                "Install gitleaks before running a real sync.")
            return
        repos = self._checked_repos()
        preview = self._diff_preview(repos=repos)
        scope = "selected repos" if len(repos) < len(self._row_widgets) else "all repos"
        detail = f"\n\nPending changes:\n{preview}" if preview else "\n\nNo uncommitted changes found."
        reply = QMessageBox.question(
            self, "Confirm sync",
            f"Commit and push changes for {scope} (after leak-gate clears each one)."
            + detail,
        )
        if reply == QMessageBox.Yes:
            self._run(dry_run=False, repos=repos)

    def _on_dry_run_single(self, name: str):
        self._run(dry_run=True, repo=name)

    def _on_sync_single(self, name: str):
        if not paths.find_gitleaks():
            QMessageBox.warning(self, "gitleaks missing",
                                "Install gitleaks before running a real sync.")
            return
        preview = self._diff_preview(name)
        detail = f"\n\nPending changes:\n{preview}" if preview else ""
        reply = QMessageBox.question(
            self, "Confirm sync",
            f"Commit and push changes for '{name}' (after leak-gate clears it)." + detail,
        )
        if reply == QMessageBox.Yes:
            self._run(dry_run=False, repo=name)

    def _run(self, *, dry_run: bool, repo: str | None = None, repos: list | None = None):
        if self.runner.is_running():
            return
        self._current_dry_run = dry_run
        self._current_single_repo = repo
        self._current_repos = repos  # None means all
        self.output_pane.clear()
        self.summary_label.hide()
        self.dry_run_btn.setEnabled(False)
        self.sync_btn.setEnabled(False)
        self._set_all_row_buttons_enabled(False)
        # For a subset of repos, run them sequentially via --repo flag.
        # For a single repo or all repos, use existing path.
        if repos is not None and len(repos) == 1:
            repo = repos[0]
            repos = None
        if repos is not None and len(repos) < len(self._row_widgets):
            self._run_subset(dry_run=dry_run, repos=repos)
        else:
            self.runner.start(
                dry_run=dry_run,
                repo=repo,
                config_path=self.config_path,
                gitleaks_cmd=self.gitleaks_cmd,
                commit_message=self.msg_field.text().strip() or None,
            )

    def _run_subset(self, *, dry_run: bool, repos: list[str]):
        """Run the engine once per selected repo, collecting all output."""
        self._subset_repos = list(repos)
        self._subset_index = 0
        self._subset_dry_run = dry_run
        self._subset_summaries: list[dict] = []
        self._run_next_subset()

    def _run_next_subset(self):
        if self._subset_index >= len(self._subset_repos):
            self._finish_subset()
            return
        repo = self._subset_repos[self._subset_index]
        self._subset_index += 1
        self.runner.start(
            dry_run=self._subset_dry_run,
            repo=repo,
            config_path=self.config_path,
            gitleaks_cmd=self.gitleaks_cmd,
            commit_message=self.msg_field.text().strip() or None,
        )
        # Temporarily override finished handler for subset mode
        try:
            self.runner.finished.disconnect(self._on_finished)
        except RuntimeError:
            pass
        self.runner.finished.connect(self._on_subset_repo_finished)

    def _on_subset_repo_finished(self, exit_code: int, summary: dict):
        self._subset_summaries.append(summary)
        try:
            self.runner.finished.disconnect(self._on_subset_repo_finished)
        except RuntimeError:
            pass
        self.runner.finished.connect(self._on_finished)
        self._run_next_subset()

    def _finish_subset(self):
        # Merge summaries
        merged_repos = {}
        merged_counts = {"synced": 0, "blocked": 0, "skipped": 0, "errors": 0, "noop": 0}
        merged_findings = {}
        worst_exit = 0
        for s in self._subset_summaries:
            merged_repos.update(s.get("repos", {}))
            merged_findings.update(s.get("findings", {}))
            c = s.get("counts") or {}
            for k in merged_counts:
                merged_counts[k] += c.get(k, 0)
        merged = {"repos": merged_repos, "counts": merged_counts, "findings": merged_findings}
        self._on_finished(worst_exit, merged)

    def _append_output(self, text: str):
        self.output_pane.appendPlainText(_ANSI_RE.sub("", text).rstrip("\n"))

    def _on_finished(self, exit_code: int, summary: dict):
        self.dry_run_btn.setEnabled(True)
        self._check_gitleaks()
        self._set_all_row_buttons_enabled(True)

        if not self._current_dry_run:
            self._refresh_last_sync_label()
            synced_now = [n for n, i in summary["repos"].items() if i["status"] == "SYNCED"]
            repo_state.record_synced(synced_now)

        self._last_findings = summary.get("findings", {})

        # Update row badges and time labels
        for name, row in self._row_widgets.items():
            info = summary["repos"].get(name)
            if info:
                row.set_status(info["status"])
            time_str = repo_state.time_since_synced(name)
            row.set_time(time_str, stale=repo_state.is_stale(name))

        # Leak report in output pane
        blocked = {n: f for n, f in self._last_findings.items()
                   if summary["repos"].get(n, {}).get("status") == "BLOCKED"}
        if blocked:
            lines = ["", "── Leak report ─────────────────────────────"]
            for name, f in blocked.items():
                lines.append(f"⛔  {name}")
                if f.get("file"):
                    rule = f"  rule: {f['rule']}" if f.get("rule") else ""
                    lines.append(f"     File: {f['file']}{rule}")
                if f.get("fingerprint"):
                    lines.append(f"     Fingerprint: {f['fingerprint']}")
            lines.append("─────────────────────────────────────────────")
            lines.append("Use the 'Ignore' button on the repo row to whitelist false positives.")
            self.output_pane.appendPlainText("\n".join(lines))

        # Update "Ignore" button availability on blocked rows (via privacy_btn slot reuse
        # isn't ideal — we surface this through a right-click or just rely on the leak report)

        counts = summary["counts"]
        if counts:
            c = counts
            text = (f"synced {c['synced']} · blocked {c['blocked']} · "
                    f"skipped {c['skipped']} · errors {c['errors']} · "
                    f"no-op {c['noop']}")
        else:
            text = "Run finished — see output for details."

        if exit_code != 0:
            self.summary_label.setStyleSheet(
                "background:#FFE5E3; color:#C0392B; padding:8px 12px;"
                " border:1px solid #FFCDD2; border-radius:8px;"
            )
            text = "⚠  Some repos were blocked or errored.  " + text
        else:
            self.summary_label.setStyleSheet(
                "background:#D1F2DC; color:#1A7A3A; padding:8px 12px;"
                " border:1px solid #A8E6B8; border-radius:8px;"
            )
        self.summary_label.setText(text)
        self.summary_label.show()
        self._refresh_tray_icon()

        # macOS notification
        if not self._current_dry_run:
            self._notify(exit_code, summary.get("counts"))

    def _notify(self, exit_code: int, counts: dict | None):
        if counts:
            body = (f"Synced {counts['synced']}, blocked {counts['blocked']}, "
                    f"skipped {counts['skipped']}")
        else:
            body = "Run complete — check the app for details."
        subtitle = "All clear" if exit_code == 0 else "Action needed"
        subprocess.Popen(
            ["osascript", "-e",
             f'display notification "{body}" with title "git_autosync" subtitle "{subtitle}"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

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

    def _on_privacy_single(self, name: str):
        gh = paths.find_gh()
        if not gh:
            QMessageBox.warning(self, "gh not found",
                                "Install the GitHub CLI first: brew install gh")
            return
        try:
            login_r = subprocess.run([gh, "api", "user", "--jq", ".login"],
                                     capture_output=True, text=True, timeout=10)
            login = login_r.stdout.strip()
            if not login:
                QMessageBox.warning(self, "Not authenticated",
                                    "Run 'gh auth login' first.")
                return
            vis_r = subprocess.run(
                [gh, "api", f"repos/{login}/{name}", "--jq", ".visibility"],
                capture_output=True, text=True, timeout=10,
            )
            current = vis_r.stdout.strip().lower()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not fetch visibility:\n{e}")
            return

        if current not in ("public", "private"):
            QMessageBox.warning(self, "Error",
                                f"Unexpected visibility '{current}'. "
                                "Make sure the repo exists and gh is authenticated.")
            return

        target = "private" if current == "public" else "public"
        if QMessageBox.question(
            self, "Change visibility",
            f"'{name}' is currently {current.upper()}. Make it {target.upper()}?",
        ) != QMessageBox.Yes:
            return

        try:
            r = subprocess.run(
                [gh, "repo", "edit", f"{login}/{name}",
                 "--visibility", target, "--accept-visibility-change-consequences"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                QMessageBox.information(self, "Done", f"'{name}' is now {target.upper()}.")
            else:
                QMessageBox.warning(self, "Failed", f"gh repo edit failed:\n{r.stderr.strip()}")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_open_ignore(self, name: str):
        lab = paths.lab_active_dir()
        repo_path = lab / name
        if not repo_path.is_dir():
            QMessageBox.warning(self, "Not found", f"Could not find repo directory for '{name}'.")
            return
        finding = self._last_findings.get(name)
        dialog = IgnoreDialog(self, repo_path, finding=finding)
        dialog.exec()

    def _on_open_logs(self):
        subprocess.run(["open", str(paths.user_log_dir())])

    def _on_toggle_tooltips(self, enabled: bool):
        self.tooltips_btn.setText("Tooltips: on" if enabled else "Tooltips")
        self._apply_tooltips(enabled)

    def _apply_tooltips(self, enabled: bool):
        pairs = [
            (self.dry_run_btn,    "dry_run_btn"),
            (self.sync_btn,       "sync_btn"),
            (self.edit_btn,       "edit_btn"),
            (self.create_repo_btn,"create_repo_btn"),
            (self.open_logs_btn,  "open_logs_btn"),
            (self.tooltips_btn,   "tooltips_btn"),
            (self.docs_btn,       "docs_btn"),
            (self.schedule_btn,   "schedule_btn"),
            (self.msg_field,      "msg_field"),
        ]
        for widget, key in pairs:
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
            DocumentationDialog(self, readme.read_text()).exec()
        else:
            QMessageBox.information(self, "Documentation",
                                    "README.md wasn't found alongside the app.")

    # ── System tray ───────────────────────────────────────────────

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

        QApplication.instance().setQuitOnLastWindowClosed(False)

        self._tray_timer = QTimer(self)
        self._tray_timer.timeout.connect(self._on_tray_tick)
        self._tray_timer.start(60_000)

    def _status_icon(self, status: str | None) -> QIcon:
        color = TRAY_COLORS.get(status, TRAY_COLORS[None])
        px = QPixmap(32, 32)
        px.fill(Qt.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(4, 4, 24, 24)
        p.end()
        return QIcon(px)

    def _refresh_tray_icon(self):
        if not self._tray:
            return
        status = paths.read_last_status()
        self._tray.setIcon(self._status_icon(status))
        stamp = paths.read_last_sync()
        label = {"ok": "all clear", "attention": "needs attention"}.get(status, "no runs yet")
        self._tray.setToolTip(
            f"git_autosync — {label}" + (f"\nLast sync: {stamp}" if stamp else "")
        )

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
