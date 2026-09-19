"""Reconcile the repo list against what is actually on disk.

The list lives in ~/Library/Application Support/, seeded once on first run and
never revisited, so a folder reorg silently rots it: entries keep pointing at
paths that no longer exist and the rows still look clickable. This dialog is
the missing half — it finds repos that moved, entries that are gone, and repos
that were never added.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QLabel, QScrollArea, QVBoxLayout,
    QWidget,
)

from . import config, paths


def _relocate_candidate(entry: str, discovered: list[str]) -> str | None:
    """A discovered repo whose basename matches a missing entry's basename.

    Catches the common reorg — convert_epub -> toolbox/convert_epub — but not a
    rename (create_and_publish -> imprint), which no heuristic should guess.
    """
    base = entry.rstrip("/").split("/")[-1]
    matches = [d for d in discovered if d.split("/")[-1] == base]
    return matches[0] if len(matches) == 1 else None


def plan_changes(entries: list[str], discovered: list[str]) -> dict:
    """Work out what reconciling would do, without touching anything."""
    missing = [e for e in entries if not paths.repo_exists(e)]
    known = set(entries)
    relocate, drop = {}, []
    for e in missing:
        target = _relocate_candidate(e, discovered)
        if target and target not in known:
            relocate[e] = target
        else:
            drop.append(e)
    resolved = {relocate.get(e, e) for e in entries}
    new = [d for d in discovered if d not in resolved]
    return {"relocate": relocate, "drop": drop, "new": new}


class RescanDialog(QDialog):
    def __init__(self, parent, config_path):
        super().__init__(parent)
        self.setWindowTitle("Find repos")
        self.setMinimumWidth(560)
        self.config_path = config_path

        self.entries = config.read_repos(config_path)
        discovered = paths.discover_repos()
        self.plan = plan_changes(self.entries, discovered)
        self._boxes: dict[str, QCheckBox] = {}

        outer = QVBoxLayout(self)
        outer.setSpacing(10)

        n = (len(self.plan["relocate"]) + len(self.plan["drop"])
             + len(self.plan["new"]))
        if n == 0:
            outer.addWidget(QLabel(
                "The list matches what is on disk — nothing to reconcile."))
        else:
            head = QLabel(
                f"Found {len(discovered)} git repositories in your projects "
                f"folder. {n} of them differ from your list — tick what to "
                f"apply, then press Apply:")
            head.setWordWrap(True)
            outer.addWidget(head)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)

        self._section(body_layout, "Moved — still here, but in a different folder (path will be fixed)",
                      [(f"reloc:{k}", f"{k}  →  {v}")
                       for k, v in self.plan["relocate"].items()])
        self._section(body_layout, "Gone — no longer on this Mac (will be removed from the list)",
                      [(f"drop:{e}", f"{e}  →  remove from list")
                       for e in self.plan["drop"]])
        self._section(body_layout, "Not in your list yet — found on disk (will be added)",
                      [(f"add:{d}", d) for d in self.plan["new"]])
        body_layout.addStretch(1)

        # Paint the panel explicitly: inheriting the window's palette gave dark
        # text on a dark ground here, which was unreadable.
        body.setObjectName("rescanBody")
        body.setStyleSheet(
            "#rescanBody { background:#FFFFFF; }"
            "#rescanBody QLabel { color:#1D1D1F; background:transparent; }"
            "#rescanBody QCheckBox { color:#1D1D1F; background:transparent;"
            " padding:2px 0; }"
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setMinimumHeight(260)
        scroll.setStyleSheet(
            "QScrollArea { background:#FFFFFF; border:1px solid #E5E5EA;"
            " border-radius:8px; }"
            "QScrollArea > QWidget > QWidget { background:#FFFFFF; }"
        )
        outer.addWidget(scroll, stretch=1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Apply")
        btns.button(QDialogButtonBox.Ok).setEnabled(n > 0)
        btns.accepted.connect(self._apply)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _section(self, layout, title: str, rows: list[tuple[str, str]]):
        if not rows:
            return
        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight:700; color:#1D1D1F; background:transparent; margin-top:10px;")
        layout.addWidget(lbl)
        for key, text in rows:
            cb = QCheckBox(text)
            cb.setChecked(True)
            self._boxes[key] = cb
            layout.addWidget(cb)

    def _apply(self):
        result: list[str] = []
        for e in self.entries:
            if e in self.plan["relocate"] and self._ticked(f"reloc:{e}"):
                result.append(self.plan["relocate"][e])
            elif e in self.plan["drop"] and self._ticked(f"drop:{e}"):
                continue          # removed
            else:
                result.append(e)
        for d in self.plan["new"]:
            if self._ticked(f"add:{d}"):
                result.append(d)
        config.write_repos(self.config_path, result)
        self.accept()

    def _ticked(self, key: str) -> bool:
        box = self._boxes.get(key)
        return bool(box and box.isChecked())
