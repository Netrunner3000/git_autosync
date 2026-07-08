"""Dialog for creating a new GitHub remote for a local project that doesn't
have one yet. Reuses git_autosync.sh's --create-remote mode so the same
leak-gate runs before anything is ever pushed — this dialog never pushes
on its own."""
import subprocess

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from . import config, paths
from .runner import AutosyncRunner

BROWSE_SENTINEL = "Browse for another folder…"


class CreateRepoDialog(QDialog):
    def __init__(self, parent, config_path, gitleaks_cmd: str):
        super().__init__(parent)
        self.setWindowTitle("Create GitHub repo")
        self.resize(560, 480)
        self.config_path = config_path
        self.gitleaks_cmd = gitleaks_cmd
        self.runner = AutosyncRunner(self)
        self.runner.output_received.connect(self._append_output)
        self.runner.finished.connect(self._on_finished)
        self._selected_dir = None
        self._gh_login = self._fetch_gh_login()

        self._build_ui()
        self._populate_candidates()
        self._check_gh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.gh_banner = QLabel()
        self.gh_banner.setWordWrap(True)
        self.gh_banner.setStyleSheet(
            "background:#fff3cd; color:#664d03; padding:8px; border-radius:4px;"
        )
        self.gh_banner.hide()
        layout.addWidget(self.gh_banner)

        form = QFormLayout()
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        form.addRow("Project:", self.project_combo)

        self.name_edit = QLineEdit()
        form.addRow("Repo name:", self.name_edit)

        self.visibility_combo = QComboBox()
        self.visibility_combo.addItems(["Private (recommended)", "Public"])
        form.addRow("Visibility:", self.visibility_combo)

        layout.addLayout(form)

        self.create_btn = QPushButton("Create & Publish")
        self.create_btn.clicked.connect(self._on_create)
        layout.addWidget(self.create_btn)

        layout.addWidget(QLabel("Output:"))
        self.output_pane = QPlainTextEdit()
        self.output_pane.setReadOnly(True)
        layout.addWidget(self.output_pane, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Close).clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_candidates(self):
        self.project_combo.clear()
        candidates = paths.repos_without_remote()
        if not candidates:
            self.project_combo.addItem("No local repos without a GitHub remote found")
            self.project_combo.setEnabled(False)
        else:
            for d in candidates:
                self.project_combo.addItem(d.name, str(d))
        self.project_combo.addItem(BROWSE_SENTINEL)

    def _on_project_changed(self, index: int):
        text = self.project_combo.currentText()
        if text == BROWSE_SENTINEL:
            chosen = QFileDialog.getExistingDirectory(self, "Choose a project folder")
            if not chosen:
                self.project_combo.setCurrentIndex(0)
                return
            from pathlib import Path

            chosen_path = Path(chosen)
            if not (chosen_path / ".git").is_dir():
                QMessageBox.warning(self, "Not a git repo", f"{chosen} has no .git folder.")
                self.project_combo.setCurrentIndex(0)
                return
            self.project_combo.insertItem(self.project_combo.count() - 1, chosen_path.name, str(chosen_path))
            self.project_combo.setCurrentIndex(self.project_combo.count() - 2)
            return

        data = self.project_combo.currentData()
        self._selected_dir = data
        if data:
            from pathlib import Path

            self.name_edit.setText(Path(data).name)

    def _check_gh(self):
        found = paths.find_gh()
        if not found:
            self.gh_banner.setText(
                "GitHub CLI (gh) not found. Install it to create repos from here:\n"
                "brew install gh   then   gh auth login"
            )
            self.gh_banner.show()
            self.create_btn.setEnabled(False)
        elif not self._gh_login:
            self.gh_banner.setText("gh is installed but not authenticated. Run: gh auth login")
            self.gh_banner.show()
            self.create_btn.setEnabled(False)
        else:
            self.gh_banner.hide()
            self.create_btn.setEnabled(True)

    def _fetch_gh_login(self) -> str | None:
        gh = paths.find_gh()
        if not gh:
            return None
        try:
            result = subprocess.run(
                [gh, "api", "user", "--jq", ".login"],
                capture_output=True, text=True, timeout=10,
            )
            login = result.stdout.strip()
            return login or None
        except Exception:
            return None

    def _on_create(self):
        if not self._selected_dir:
            QMessageBox.warning(self, "No project selected", "Choose a project first.")
            return
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "No name", "Enter a repo name.")
            return
        visibility = "private" if self.visibility_combo.currentIndex() == 0 else "public"

        reply = QMessageBox.question(
            self,
            "Confirm",
            f"This will scan '{name}' for secrets, then — only if clean — create a "
            f"{visibility.upper()} GitHub repo named '{name}' and push to it.\n\n"
            "Continue?",
        )
        if reply != QMessageBox.Yes:
            return

        repos = config.read_repos(self.config_path)
        if self._selected_dir not in repos:
            repos.append(self._selected_dir)
            config.write_repos(self.config_path, repos)

        self.output_pane.clear()
        self.create_btn.setEnabled(False)
        self.runner.start(
            dry_run=False,
            repo=name,
            config_path=self.config_path,
            gitleaks_cmd=self.gitleaks_cmd,
            create_remote=visibility,
        )

    def _append_output(self, text: str):
        self.output_pane.appendPlainText(text.rstrip("\n"))

    def _on_finished(self, exit_code: int, summary: dict):
        self.create_btn.setEnabled(True)
        name = self.name_edit.text().strip()
        info = summary["repos"].get(name)
        if exit_code == 0 and info and info["status"] == "SYNCED":
            url = f"https://github.com/{self._gh_login}/{name}" if self._gh_login else "(see GitHub)"
            QMessageBox.information(self, "Created", f"Repo created and pushed:\n{url}")
        else:
            detail = info["detail"] if info else "see output above"
            QMessageBox.warning(self, "Not created", f"Repo was not created/pushed: {detail}")
