"""Modern Apple-inspired stylesheet for git_autosync."""

ACCENT        = "#0d6e5c"
ACCENT_DARK   = "#0a5a4a"
ACCENT_LIGHT  = "#E8F5F2"

STYLESHEET = f"""
/* ── Globals ───────────────────────────────────────────────── */
QWidget {{
    font-size: 13px;
    color: #1D1D1F;
}}
QMainWindow, QDialog {{
    background: #F5F5F7;
}}

/* ── Scrollbars ─────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #C7C7CC;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

/* ── Buttons ────────────────────────────────────────────────── */
QPushButton {{
    background: #FFFFFF;
    border: 1px solid #D1D1D6;
    border-radius: 7px;
    padding: 6px 14px;
    color: #1D1D1F;
    font-weight: 500;
}}
QPushButton:hover  {{ background: #F2F2F7; border-color: #AEAEB2; }}
QPushButton:pressed {{ background: #E5E5EA; }}
QPushButton:disabled {{ color: #AEAEB2; background: #F5F5F7; border-color: #E5E5EA; }}

QPushButton#primaryButton {{
    background: {ACCENT};
    border-color: {ACCENT_DARK};
    color: white;
    font-weight: 600;
    font-size: 14px;
    padding: 8px 24px;
}}
QPushButton#primaryButton:hover   {{ background: {ACCENT_DARK}; }}
QPushButton#primaryButton:disabled {{
    background: #A8C5BF;
    border-color: #A8C5BF;
    color: #E8F5F2;
}}

QPushButton#secondaryButton {{
    background: #FFFFFF;
    border: 1px solid #D1D1D6;
    padding: 8px 16px;
    font-size: 13px;
}}

QPushButton[class="rowButton"] {{
    padding: 3px 9px;
    font-size: 11px;
    border-radius: 5px;
    font-weight: 400;
    color: #3A3A3C;
    background: #F2F2F7;
    border-color: #E5E5EA;
}}
QPushButton[class="rowButton"]:hover  {{ background: #E5E5EA; }}
QPushButton[class="rowButton"]:pressed {{ background: #D8D8DC; }}
QPushButton[class="rowButton"]:disabled {{ color: #AEAEB2; background: #F5F5F7; }}

QPushButton:checkable:checked {{
    background: {ACCENT_LIGHT};
    border-color: {ACCENT};
    color: {ACCENT_DARK};
    font-weight: 600;
}}

/* ── List widget ────────────────────────────────────────────── */
QListWidget {{
    background: white;
    border: 1px solid #E5E5EA;
    border-radius: 10px;
    outline: 0;
}}
QListWidget::item {{
    border-bottom: 1px solid #F2F2F7;
    padding: 0;
}}
QListWidget::item:last-child  {{ border-bottom: none; }}
QListWidget::item:selected    {{ background: transparent; }}
QListWidget QLabel            {{ color: #1D1D1F; background: transparent; }}

/* ── Text / input ───────────────────────────────────────────── */
QPlainTextEdit {{
    background: #1C1C1E;
    color: #E5E5EA;
    border: 1px solid #3A3A3C;
    border-radius: 10px;
    font-family: "SF Mono", Menlo, monospace;
    font-size: 12px;
    padding: 6px;
}}
QLineEdit {{
    background: white;
    border: 1px solid #D1D1D6;
    border-radius: 7px;
    padding: 6px 10px;
    color: #1D1D1F;
}}
QLineEdit:focus  {{ border-color: {ACCENT}; }}
QLineEdit:disabled {{ background: #F5F5F7; color: #AEAEB2; }}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel#sectionLabel {{
    color: #6E6E73;
    font-weight: 600;
    font-size: 11px;
}}
QLabel#repoName {{
    font-weight: 500;
    color: #1D1D1F;
    font-size: 13px;
}}

/* ── Status bar ─────────────────────────────────────────────── */
QStatusBar {{
    background: #F5F5F7;
    border-top: 1px solid #E5E5EA;
    font-size: 12px;
    color: #6E6E73;
}}

/* ── Combo / form ───────────────────────────────────────────── */
QComboBox {{
    background: white;
    border: 1px solid #D1D1D6;
    border-radius: 7px;
    padding: 5px 10px;
    color: #1D1D1F;
}}
QComboBox::drop-down {{ border: none; }}

/* ── Dialog buttons ─────────────────────────────────────────── */
QDialogButtonBox QPushButton {{
    min-width: 72px;
}}
"""
