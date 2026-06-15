# main.py — Application entry point

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

from theme import GLOBAL_STYLESHEET
from judge import JudgeTab
from ollama_setup import OllamaSetup


class MainApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CP Judge & Test Generator")
        self.setStyleSheet(GLOBAL_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.judgeTab = JudgeTab()
        self.judgeTab.parent_app = self
        layout.addWidget(self.judgeTab, 1)

        self._setup = OllamaSetup()
        self._setup.ensure(
            on_status=lambda msg: None,
            on_ready=lambda: None,
            on_error=lambda msg: None,
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainApp()
    w.resize(1280, 800)
    w.show()
    sys.exit(app.exec())