# main.py — Application entry point (with automatic Ollama setup)

import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTabWidget,
    QPushButton, QHBoxLayout,
)

from theme import GLOBAL_STYLESHEET, ACCENT, BG3, BORDER_BRIGHT, TEXT_HINT, RED, AMBER, GREEN, FONT_UI
from judge import JudgeTab
from generator import GeneratorTab
from ollama_setup import OllamaSetup


class MainApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CP Judge & Test Generator")
        self.setStyleSheet(GLOBAL_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────
        topbar = QWidget()
        topbar.setFixedHeight(42)
        topbar.setStyleSheet(
            f"QWidget {{ background:{BG3}; border-bottom:1px solid {BORDER_BRIGHT}; }}"
        )
        tbl = QHBoxLayout(topbar)
        tbl.setContentsMargins(0, 0, 10, 0)
        tbl.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border:none; }"
            f"QTabBar::tab {{ background:{BG3}; color:{TEXT_HINT}; padding:10px 20px;"
            f"  font-size:13px; font-weight:700; border:none; }}"
            f"QTabBar::tab:selected {{ color:{ACCENT}; border-bottom:2px solid {ACCENT}; }}"
        )

        self.judgeTab = JudgeTab()
        self.genTab   = GeneratorTab()
        self.judgeTab.parent_app = self
        self.genTab.parent_app   = self

        self.tabs.addTab(self.judgeTab, "⚖  Judge")
        self.tabs.addTab(self.genTab,   "⚙  Generator")
        tbl.addWidget(self.tabs, 1)

        # AI status pill in top-right corner
        self._aiPill = QPushButton("⬤  AI setting up…")
        self._aiPill.setEnabled(False)
        self._aiPill.setFixedHeight(28)
        self._pill_style(AMBER)
        tbl.addWidget(self._aiPill)

        layout.addWidget(topbar)
        layout.addWidget(self.tabs, 1)

        # ── Start Ollama auto-setup in background ─────────────
        self._setup = OllamaSetup()
        self._setup.ensure(
            on_status = self._on_ai_status,
            on_ready  = self._on_ai_ready,
            on_error  = self._on_ai_error,
        )

    def _pill_style(self, color):
        self._aiPill.setStyleSheet(
            f"QPushButton {{ background:{color}18; color:{color};"
            f"  border:1px solid {color}55; border-radius:6px;"
            f"  font-family:{FONT_UI}; font-size:11px; font-weight:600; padding:0 12px; }}"
        )

    def _on_ai_status(self, msg: str):
        self._aiPill.setText(f"⬤  {msg}")
        self._pill_style(AMBER)

    def _on_ai_ready(self):
        self._aiPill.setText("⬤  AI ready")
        self._pill_style(GREEN)

    def _on_ai_error(self, msg: str):
        self._aiPill.setText("⬤  AI unavailable")
        self._aiPill.setToolTip(msg)   # hover to see the error
        self._pill_style(RED)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainApp()
    w.resize(1280, 800)
    w.show()
    sys.exit(app.exec())