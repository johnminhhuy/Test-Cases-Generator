# theme.py — Design tokens and shared stylesheet helpers

# ── Colours ───────────────────────────────────────────────────
BG0   = "#080c10"
BG1   = "#0d1219"
BG2   = "#111823"
BG3   = "#1a2535"
BORDER = "#1e2d42"
BORDER_BRIGHT = "#2a4060"
TEXT_MAIN  = "#c8dce8"
TEXT_DIM   = "#5a7a94"
TEXT_HINT  = "#3a5a70"
ACCENT     = "#3b9ede"
ACCENT_DIM = "#1a4a6e"
GREEN      = "#4ec94e"
GREEN_DIM  = "#1a4a1a"
RED        = "#e84e4e"
RED_DIM    = "#4a1a1a"
AMBER      = "#e8a83b"
AMBER_DIM  = "#4a320a"

# ── Fonts ─────────────────────────────────────────────────────
FONT_MONO = "JetBrains Mono, Fira Code, Consolas, monospace"
FONT_UI   = "IBM Plex Sans, Segoe UI, sans-serif"

# ── Per-variable colour slots ─────────────────────────────────
VAR_PALETTE = [
    ("#0d2540", "#5bc8f5", "#1e6a9e"),
    ("#152510", "#7ed45a", "#3a6a1e"),
    ("#200d40", "#c85bf5", "#6a1e9e"),
    ("#2a1f08", "#f5a63b", "#9e6a1e"),
    ("#2a1010", "#f5605b", "#9e2a1e"),
    ("#0d2a2a", "#5bf5e0", "#1e9e8a"),
    ("#1a0d2a", "#a07ef5", "#5a3e9e"),
    ("#24200d", "#d4c45a", "#8a7a1e"),
]

def palette_for(i):
    return VAR_PALETTE[i % len(VAR_PALETTE)]


# ── Stylesheet helpers ────────────────────────────────────────
def card_style(border_color=BORDER):
    return (
        f"background:{BG2}; border:1px solid {border_color};"
        f"border-radius:6px;"
    )

def label_style(dim=False):
    col = TEXT_DIM if dim else TEXT_MAIN
    return f"color:{col}; background:transparent; border:none; font-family:{FONT_UI};"

def section_label_style():
    return (
        f"color:{TEXT_MAIN}; background:transparent; border:none;"
        f"font-family:{FONT_UI}; font-size:12px; font-weight:700;"
        f"letter-spacing:1px;"
    )

def editor_style(border=BORDER, focus_border=ACCENT):
    return (
        f"QTextEdit {{ background:{BG1}; color:{TEXT_MAIN};"
        f"  border:1px solid {border}; border-radius:5px;"
        f"  font-family:{FONT_MONO}; font-size:12px; padding:6px;"
        f"  selection-background-color:{ACCENT_DIM}; }}"
        f"QTextEdit:focus {{ border-color:{focus_border}; }}"
    )

def line_edit_style(width=None):
    w = f"width:{width}px;" if width else ""
    return (
        f"QLineEdit {{ background:{BG1}; color:{TEXT_MAIN}; {w}"
        f"  border:1px solid {BORDER}; border-radius:4px;"
        f"  font-family:{FONT_MONO}; font-size:12px; padding:3px 7px; }}"
        f"QLineEdit:focus {{ border-color:{ACCENT}; }}"
        f"QLineEdit:disabled {{ color:{TEXT_HINT}; }}"
    )

def btn_primary():
    return (
        f"QPushButton {{ background:{ACCENT_DIM}; color:{ACCENT};"
        f"  border:1px solid {ACCENT}; border-radius:5px;"
        f"  font-family:{FONT_UI}; font-size:12px; font-weight:600;"
        f"  padding:6px 14px; }}"
        f"QPushButton:hover {{ background:{ACCENT}; color:#fff; }}"
        f"QPushButton:disabled {{ background:{BG2}; color:{TEXT_HINT}; border-color:{BORDER}; }}"
    )

def btn_ghost():
    return (
        f"QPushButton {{ background:transparent; color:{TEXT_DIM};"
        f"  border:1px solid {BORDER}; border-radius:5px;"
        f"  font-family:{FONT_UI}; font-size:11px; padding:5px 12px; }}"
        f"QPushButton:hover {{ border-color:{ACCENT}; color:{ACCENT}; }}"
        f"QPushButton:disabled {{ color:{TEXT_HINT}; border-color:{BORDER}; }}"
    )

def btn_danger():
    return (
        f"QPushButton {{ background:transparent; color:{RED};"
        f"  border:1px solid {RED_DIM}; border-radius:5px;"
        f"  font-family:{FONT_UI}; font-size:11px; padding:5px 12px; }}"
        f"QPushButton:hover {{ background:{RED_DIM}; border-color:{RED}; }}"
    )

def btn_green():
    return (
        f"QPushButton {{ background:{GREEN_DIM}; color:{GREEN};"
        f"  border:1px solid {GREEN}; border-radius:5px;"
        f"  font-family:{FONT_UI}; font-size:13px; font-weight:700;"
        f"  padding:8px 20px; }}"
        f"QPushButton:hover {{ background:{GREEN}; color:#000; }}"
        f"QPushButton:disabled {{ background:{BG2}; color:{TEXT_HINT}; border-color:{BORDER}; }}"
    )


GLOBAL_STYLESHEET = f"""
QWidget {{ background:{BG0}; color:{TEXT_MAIN}; font-family:{FONT_UI}; }}

QTabWidget::pane {{
    border:1px solid {BORDER};
    border-radius:6px;
    background:{BG1};
}}
QTabBar::tab {{
    background:{BG1}; color:{TEXT_DIM};
    padding:6px 20px;
    border:1px solid {BORDER};
    border-bottom:none;
    border-radius:4px 4px 0 0;
    font-size:12px; font-weight:600;
    margin-right:2px;
}}
QTabBar::tab:selected {{
    background:{BG2}; color:{ACCENT};
    border-bottom:2px solid {ACCENT};
}}

QScrollBar:vertical {{
    background:{BG1}; width:8px; border:none;
}}
QScrollBar::handle:vertical {{
    background:{BORDER_BRIGHT}; border-radius:4px; min-height:20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}

QScrollBar:horizontal {{
    background:{BG1}; height:8px; border:none;
}}
QScrollBar::handle:horizontal {{
    background:{BORDER_BRIGHT}; border-radius:4px;
}}

QListWidget {{
    background:{BG1}; border:1px solid {BORDER}; border-radius:5px;
    color:{TEXT_MAIN}; font-size:12px;
    outline:none;
}}
QListWidget::item {{
    padding:6px 10px; border-bottom:1px solid {BG2};
}}
QListWidget::item:selected {{
    background:{ACCENT_DIM}; color:{ACCENT};
    border-left:2px solid {ACCENT};
}}
QListWidget::item:hover:!selected {{
    background:{BG3};
}}

QProgressBar {{
    background:{BG1}; border:1px solid {BORDER}; border-radius:4px;
    color:transparent; height:6px;
}}
QProgressBar::chunk {{
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT}, stop:1 {GREEN});
    border-radius:4px;
}}

QSpinBox {{
    background:{BG1}; border:1px solid {BORDER}; border-radius:4px;
    color:{TEXT_MAIN}; font-size:12px; padding:3px 6px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background:{BG2}; border:none; width:18px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background:{BG3};
}}

QComboBox {{
    background:{BG1}; border:1px solid {BORDER}; border-radius:4px;
    color:{TEXT_MAIN}; font-size:12px; padding:3px 8px;
}}
QComboBox::drop-down {{ border:none; width:18px; }}
QComboBox QAbstractItemView {{
    background:{BG2}; color:{TEXT_MAIN}; border:1px solid {BORDER};
    selection-background-color:{ACCENT_DIM};
}}

QToolTip {{
    background:{BG2}; color:{TEXT_MAIN};
    border:1px solid {ACCENT_DIM}; border-radius:4px;
    padding:4px 8px; font-size:11px;
}}
"""