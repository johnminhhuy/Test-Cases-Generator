# widgets.py — Reusable UI widgets

from PySide6.QtWidgets import (
    QLabel, QFrame, QWidget, QHBoxLayout, QLineEdit,
    QPushButton, QCheckBox, QFileDialog,
)
from PySide6.QtCore import QSettings

from theme import (
    TEXT_DIM, TEXT_MAIN, TEXT_HINT, ACCENT, BORDER, BORDER_BRIGHT,
    BG2, FONT_UI, FONT_MONO,
    section_label_style, line_edit_style, btn_ghost,
)

# ── Persistent settings ───────────────────────────────────────
SETTINGS = QSettings("CPJudge", "CPJudge")


def save(key, value):
    SETTINGS.setValue(key, value)


def load(key, default=None):
    return SETTINGS.value(key, default)


# ── Simple factory widgets ────────────────────────────────────
def SectionLabel(text):
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(section_label_style())
    return lbl


def HRule():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"border:none; border-top:1px solid {BORDER};")
    line.setFixedHeight(1)
    return line


# ── File picker row ───────────────────────────────────────────
class FilePickerRow(QWidget):
    """A labelled row: [label] [text field or stdin/stdout checkbox] [Browse btn]"""

    def __init__(self, label, placeholder, stdin_label=None, settings_key=None):
        super().__init__()
        self.settings_key = settings_key
        self.setStyleSheet("background:transparent;")
        hl = QHBoxLayout()
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)

        lbl = QLabel(label)
        lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; background:transparent;")
        hl.addWidget(lbl)

        self.pathEdit = QLineEdit()
        self.pathEdit.setPlaceholderText(placeholder)
        self.pathEdit.setStyleSheet(line_edit_style())
        if settings_key:
            self.pathEdit.setText(load(settings_key + "_path", ""))
        self.pathEdit.textChanged.connect(self._onPathChanged)
        hl.addWidget(self.pathEdit, 1)

        if stdin_label:
            self.stdCheck = QCheckBox(stdin_label)
            self.stdCheck.setStyleSheet(
                f"QCheckBox {{ color:{TEXT_DIM}; font-size:11px; background:transparent; }}"
                f"QCheckBox::indicator {{ width:14px; height:14px; border:1px solid {BORDER_BRIGHT}; border-radius:3px; background:{BG2}; }}"
                f"QCheckBox::indicator:checked {{ background:{ACCENT}; border-color:{ACCENT}; }}"
            )
            if settings_key:
                self.stdCheck.setChecked(load(settings_key + "_std", False) == "true")
            self.stdCheck.toggled.connect(self._onStdToggled)
            hl.addWidget(self.stdCheck)

        self.browseBtn = QPushButton("Browse")
        self.browseBtn.setFixedWidth(70)
        self.browseBtn.setStyleSheet(btn_ghost())
        self.browseBtn.clicked.connect(self._browse)
        hl.addWidget(self.browseBtn)

        self.setLayout(hl)
        if stdin_label:
            self._onStdToggled(self.stdCheck.isChecked())

    def _onPathChanged(self, text):
        if self.settings_key:
            save(self.settings_key + "_path", text)

    def _onStdToggled(self, checked):
        self.pathEdit.setEnabled(not checked)
        self.browseBtn.setEnabled(not checked)
        if self.settings_key:
            save(self.settings_key + "_std", "true" if checked else "false")

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if path:
            self.pathEdit.setText(path)

    def value(self):
        if hasattr(self, "stdCheck") and self.stdCheck.isChecked():
            return None  # means stdin/stdout
        return self.pathEdit.text().strip() or None