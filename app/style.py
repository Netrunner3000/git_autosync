"""A light stylesheet for the GUI — consistent spacing, rounded controls, and
an accent color matching the app icon. Deliberately minimal: this changes how
existing widgets render, not the layout or information density."""

ACCENT = "#0d6e5c"
ACCENT_DARK = "#0a5a4a"
ACCENT_LIGHT = "#e6f2ef"

STYLESHEET = f"""
QWidget {{
    font-size: 13px;
}}

QMainWindow {{
    background: #f7f8f9;
}}

QPushButton {{
    background: #ffffff;
    border: 1px solid #d6d9dc;
    border-radius: 6px;
    padding: 6px 12px;
    color: #2a2e32;
}}

QPushButton:hover {{
    background: #f0f1f2;
    border-color: #c2c6ca;
}}

QPushButton:pressed {{
    background: #e6e7e8;
}}

QPushButton:disabled {{
    color: #aab0b5;
    background: #f5f5f5;
    border-color: #e2e4e6;
}}

QPushButton:checkable:checked {{
    background: {ACCENT_LIGHT};
    border-color: {ACCENT};
    color: {ACCENT_DARK};
}}

QPushButton#primaryButton {{
    background: {ACCENT};
    border-color: {ACCENT_DARK};
    color: white;
    font-weight: 600;
}}

QPushButton#primaryButton:hover {{
    background: {ACCENT_DARK};
}}

QPushButton#primaryButton:disabled {{
    background: #b9c9c5;
    border-color: #b9c9c5;
    color: #eef2f1;
}}

QPushButton[class="rowButton"] {{
    padding: 2px 8px;
    font-size: 12px;
}}

QListWidget {{
    background: white;
    border: 1px solid #e0e2e4;
    border-radius: 8px;
}}

QListWidget::item {{
    border-bottom: 1px solid #f0f1f2;
}}

QListWidget QLabel {{
    color: #2a2e32;
    background: transparent;
}}

QPlainTextEdit {{
    background: #1e1f22;
    color: #d8dadc;
    border: 1px solid #e0e2e4;
    border-radius: 8px;
    font-family: Menlo, monospace;
    font-size: 12px;
}}

QStatusBar {{
    background: #f0f1f2;
    border-top: 1px solid #e0e2e4;
}}

QLabel#sectionLabel {{
    color: #5a6066;
    font-weight: 600;
    margin-top: 4px;
}}
"""
