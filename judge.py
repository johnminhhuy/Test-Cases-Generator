# judge_tab.py — CodePanel and JudgeTab

import re
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QLineEdit, QFileDialog,
    QCheckBox, QProgressBar, QScrollArea, QFrame,
    QSplitter, QDialog, QComboBox,
)
from PySide6.QtCore import Qt, QTimer

from theme import (
    BG0, BG1, BG2, BG3, BORDER, BORDER_BRIGHT,
    TEXT_MAIN, TEXT_DIM, TEXT_HINT,
    ACCENT, ACCENT_DIM,
    GREEN, GREEN_DIM, RED, RED_DIM, AMBER, AMBER_DIM,
    FONT_MONO, FONT_UI,
    card_style, section_label_style, editor_style, line_edit_style,
    btn_primary, btn_ghost, btn_danger, btn_green,
)
from highlighters import CodeHighlighter
from widgets import save, load
from worker import TestWorker
from ai_worker import AIWorker


# ── Language constants ────────────────────────────────────────
LANG_EXT    = {"Python": ".py",   "C++": ".cpp",  "Java": ".java"}
LANG_FILTER = {"Python": "*.py",  "C++": "*.cpp", "Java": "*.java"}
LANG_COLORS = {
    "Python": ("#1a3a1a", "#4ec94e"),
    "C++":    ("#0d2a40", "#5bc8f5"),
    "Java":   ("#2a1040", "#c85bf5"),
}


def _detect_lang(code):
    """Guess language from first 512 chars of code."""
    head = code[:512]
    if re.search(r"#include|int main|std::|cout|cin|namespace", head):
        return "C++"
    if re.search(r"public class|import java|System\.out|void main", head):
        return "Java"
    if re.search(r"def |import |print\(|elif |\bself\b", head):
        return "Python"
    return None


# ── Code panel ────────────────────────────────────────────────
class CodePanel(QWidget):
    """Header bar with pill lang buttons, mismatch warning, and syntax highlighting."""

    def __init__(self, title, settings_key, placeholder=""):
        super().__init__()
        self.settings_key     = settings_key
        self._suppress_detect = False
        self.setStyleSheet(
            f"QWidget {{ background:{BG1}; border:1px solid {BORDER}; border-radius:6px; }}"
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(44)
        header.setStyleSheet(
            f"QWidget {{ background:{BG3}; border-radius:5px 5px 0 0;"
            f"  border-bottom:1px solid {BORDER}; }}"
        )
        hl = QHBoxLayout()
        hl.setContentsMargins(12, 0, 10, 0)
        hl.setSpacing(10)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color:{TEXT_MAIN}; font-size:13px; font-weight:800;"
            f"letter-spacing:1px; background:transparent;"
        )
        hl.addWidget(title_lbl)
        hl.addStretch()

        saved_lang = load(settings_key + "_lang", "Python")
        self._langBtns = {}
        for lng in ["Python", "C++", "Java"]:
            btn = QPushButton(lng)
            btn.setCheckable(True)
            btn.setChecked(lng == saved_lang)
            btn.setFixedHeight(28)
            btn.setFixedWidth(64)
            btn.clicked.connect(lambda _, l=lng: self._selectLang(l))
            self._langBtns[lng] = btn
            hl.addWidget(btn)
        self._applyLangStyles(saved_lang)

        loadBtn = QPushButton("Load File")
        loadBtn.setFixedHeight(28)
        loadBtn.setStyleSheet(btn_ghost())
        loadBtn.clicked.connect(self._loadFile)
        hl.addWidget(loadBtn)

        header.setLayout(hl)
        layout.addWidget(header)

        # Warning strip
        self._warnBar = QLabel("")
        self._warnBar.setFixedHeight(24)
        self._warnBar.setStyleSheet(
            f"background:{AMBER_DIM}; color:{AMBER}; border-bottom:1px solid {AMBER}44;"
            f"font-size:11px; font-weight:600; padding:0 10px;"
        )
        self._warnBar.setVisible(False)
        layout.addWidget(self._warnBar)

        # File path strip
        self.filePath = QLabel("")
        self.filePath.setStyleSheet(
            f"color:{TEXT_HINT}; font-size:10px; font-family:{FONT_MONO};"
            f"background:{BG2}; border-bottom:1px solid {BORDER}; padding:2px 10px;"
        )
        self.filePath.setVisible(False)
        layout.addWidget(self.filePath)

        # Editor
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(placeholder)
        self.editor.setStyleSheet(
            f"QTextEdit {{ background:{BG1}; color:{TEXT_MAIN}; border:none; border-radius:0 0 5px 5px;"
            f"  font-family:{FONT_MONO}; font-size:12px; padding:8px; }}"
        )
        self._highlighter = CodeHighlighter(self.editor.document(), saved_lang)

        saved_code = load(settings_key + "_code", "")
        if saved_code:
            self.editor.setText(saved_code)

        self.editor.textChanged.connect(self._onTextChanged)
        layout.addWidget(self.editor)

        self.setLayout(layout)

    def _selectLang(self, lang):
        for l, b in self._langBtns.items():
            b.setChecked(l == lang)
        self._applyLangStyles(lang)
        self._highlighter.set_lang(lang)
        save(self.settings_key + "_lang", lang)
        self._warnBar.setVisible(False)

    def _applyLangStyles(self, active):
        for lng, btn in self._langBtns.items():
            bg, fg = LANG_COLORS.get(lng, (BG2, TEXT_DIM))
            if lng == active:
                btn.setStyleSheet(
                    f"QPushButton {{ background:{bg}; color:{fg}; border:2px solid {fg};"
                    f"  border-radius:13px; font-size:11px; font-weight:800; }}"
                    f"QPushButton:hover {{ background:{fg}; color:#000; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background:transparent; color:{TEXT_HINT};"
                    f"  border:1px solid {BORDER}; border-radius:13px; font-size:11px; }}"
                    f"QPushButton:hover {{ border-color:{TEXT_DIM}; color:{TEXT_DIM}; }}"
                )

    def _onTextChanged(self):
        code = self.editor.toPlainText()
        save(self.settings_key + "_code", code)
        if not self._suppress_detect and len(code) > 30:
            detected = _detect_lang(code)
            current  = self.lang()
            if detected and detected != current:
                self._warnBar.setText(
                    f"  ⚠  Looks like {detected} — but {current} is selected. "
                    f"Click the right language button above."
                )
                self._warnBar.setVisible(True)
            else:
                self._warnBar.setVisible(False)

    def _loadFile(self):
        lang = self.lang()
        flt  = f"{LANG_FILTER.get(lang, '*.py')};;All Files (*)"
        file, _ = QFileDialog.getOpenFileName(self, f"Load {lang} File", "", flt)
        if file:
            ext      = file.rsplit(".", 1)[-1].lower() if "." in file else ""
            ext_lang = {"py": "Python", "cpp": "C++", "java": "Java"}.get(ext)
            if ext_lang:
                self._selectLang(ext_lang)
            with open(file, "r", encoding="utf-8") as f:
                self._suppress_detect = True
                self.editor.setText(f.read())
                self._suppress_detect = False
            self.filePath.setText(f"  {file}")
            self.filePath.setVisible(True)
            save(self.settings_key + "_filepath", file)

    def code(self):
        return self.editor.toPlainText()

    def lang(self):
        for lng, btn in self._langBtns.items():
            if btn.isChecked():
                return lng
        return "Python"


# ── Judge Tab ─────────────────────────────────────────────────
class JudgeTab(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout()
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        # Code panels
        code_row = QHBoxLayout()
        code_row.setSpacing(8)
        self.userPanel = CodePanel("USER CODE",   "judge_user", placeholder="Paste or load user solution here…")
        self.ansPanel  = CodePanel("ANSWER CODE", "judge_ans",  placeholder="Paste or load reference / judge solution here…")
        code_row.addWidget(self.userPanel)
        code_row.addWidget(self.ansPanel)
        root.addLayout(code_row, 3)

        # Config card
        root.addWidget(self._buildConfigCard())

        # Run bar
        run_bar = QHBoxLayout()
        run_bar.setSpacing(10)
        self.runBtn = QPushButton("▶  Run Tests")
        self.runBtn.setStyleSheet(btn_green())
        self.runBtn.setFixedHeight(40)
        self.runBtn.clicked.connect(self.runTests)
        run_bar.addWidget(self.runBtn)
        self.progressBar = QProgressBar()
        self.progressBar.setValue(0)
        self.progressBar.setFixedHeight(8)
        run_bar.addWidget(self.progressBar, 1)
        self.statusLabel = QLabel("Idle")
        self.statusLabel.setStyleSheet(f"color:{TEXT_MAIN}; font-size:13px; font-weight:700; background:transparent;")
        self.statusLabel.setFixedWidth(140)
        run_bar.addWidget(self.statusLabel)
        self.resultSummary = QLabel("")
        self.resultSummary.setStyleSheet(f"color:{TEXT_DIM}; font-size:13px; font-weight:700; background:transparent;")
        run_bar.addWidget(self.resultSummary)
        
        # AI buttons
        ai_bar = QHBoxLayout()
        ai_bar.setSpacing(12)
        self.generateJsonBtn = QPushButton("📄 Generate Test JSON")
        self.generateJsonBtn.setStyleSheet(btn_primary())
        self.generateJsonBtn.setFixedHeight(36)
        self.generateJsonBtn.clicked.connect(self._generateTestJSON)
        self.generateAnswerBtn = QPushButton("💻 Generate Answer Code")
        self.generateAnswerBtn.setStyleSheet(btn_primary())
        self.generateAnswerBtn.setFixedHeight(36)
        self.generateAnswerBtn.clicked.connect(self._generateAnswerCode)
        ai_bar.addStretch()
        ai_bar.addWidget(self.generateJsonBtn)
        ai_bar.addWidget(self.generateAnswerBtn)
        root.addLayout(ai_bar)
        
        root.addLayout(run_bar)

        # Results header + splitter
        root.addWidget(self._buildResultsHeader())
        root.addWidget(self._buildResultsSplitter(), 3)

        self.setLayout(root)
        self._all_results = []
        self._onStdinToggled(self.stdinCheck.isChecked())
        self._onStdoutToggled(self.stdoutCheck.isChecked())

    # ── Config card ───────────────────────────────────────────
    def _buildConfigCard(self):
        config_card = QWidget()
        config_card.setStyleSheet(f"QWidget {{ {card_style(BORDER_BRIGHT)} }}")
        cfg = QVBoxLayout()
        cfg.setContentsMargins(12, 10, 12, 10)
        cfg.setSpacing(8)

        cfg_title = QLabel("TEST CONFIGURATION")
        cfg_title.setStyleSheet(section_label_style())
        cfg.addWidget(cfg_title)

        fields_row = QHBoxLayout()
        fields_row.setSpacing(16)

        # Time limit
        tl_col = QVBoxLayout()
        tl_col.setSpacing(3)
        tl_lbl = QLabel("Time Limit (s)")
        tl_lbl.setStyleSheet(f"color:{TEXT_MAIN}; font-size:12px; font-weight:600; background:transparent;")
        self.timeInput = QLineEdit()
        self.timeInput.setPlaceholderText("e.g. 1.0")
        self.timeInput.setFixedWidth(80)
        self.timeInput.setStyleSheet(line_edit_style())
        self.timeInput.setText(load("judge_timelimit", "1.0"))
        self.timeInput.textChanged.connect(lambda t: save("judge_timelimit", t))
        tl_col.addWidget(tl_lbl)
        tl_col.addWidget(self.timeInput)
        fields_row.addLayout(tl_col)

        # Input file
        in_col = QVBoxLayout()
        in_col.setSpacing(3)
        in_lbl = QLabel("Input File")
        in_lbl.setStyleSheet(f"color:{TEXT_MAIN}; font-size:12px; font-weight:600; background:transparent;")
        in_row2 = QHBoxLayout()
        in_row2.setSpacing(6)
        self.inputFile = QLineEdit()
        self.inputFile.setPlaceholderText("stdin")
        self.inputFile.setFixedWidth(160)
        self.inputFile.setStyleSheet(line_edit_style())
        self.inputFile.setText(load("judge_input_file", ""))
        self.inputFile.textChanged.connect(lambda t: save("judge_input_file", t))
        self.stdinCheck = QCheckBox("stdin")
        self.stdinCheck.setStyleSheet(
            f"QCheckBox {{ color:{TEXT_MAIN}; font-size:12px; font-weight:600; background:transparent; }}"
            f"QCheckBox::indicator {{ width:15px; height:15px; border:1px solid {BORDER_BRIGHT}; border-radius:3px; background:{BG2}; }}"
            f"QCheckBox::indicator:checked {{ background:{ACCENT}; border-color:{ACCENT}; }}"
        )
        stdin_saved = load("judge_stdin", "true")
        self.stdinCheck.setChecked(stdin_saved != "false")
        self.stdinCheck.toggled.connect(self._onStdinToggled)
        in_row2.addWidget(self.inputFile)
        in_row2.addWidget(self.stdinCheck)
        in_col.addWidget(in_lbl)
        in_col.addLayout(in_row2)
        fields_row.addLayout(in_col)

        # Output file
        out_col = QVBoxLayout()
        out_col.setSpacing(3)
        out_lbl = QLabel("Output File")
        out_lbl.setStyleSheet(f"color:{TEXT_MAIN}; font-size:12px; font-weight:600; background:transparent;")
        out_row2 = QHBoxLayout()
        out_row2.setSpacing(6)
        self.outputFile = QLineEdit()
        self.outputFile.setPlaceholderText("output.out")
        self.outputFile.setFixedWidth(160)
        self.outputFile.setStyleSheet(line_edit_style())
        self.outputFile.setText(load("judge_output_file", "output.out"))
        self.outputFile.textChanged.connect(lambda t: save("judge_output_file", t))
        self.stdoutCheck = QCheckBox("stdout")
        self.stdoutCheck.setStyleSheet(
            f"QCheckBox {{ color:{TEXT_MAIN}; font-size:12px; font-weight:600; background:transparent; }}"
            f"QCheckBox::indicator {{ width:15px; height:15px; border:1px solid {BORDER_BRIGHT}; border-radius:3px; background:{BG2}; }}"
            f"QCheckBox::indicator:checked {{ background:{ACCENT}; border-color:{ACCENT}; }}"
        )
        stdout_saved = load("judge_stdout", "false")
        self.stdoutCheck.setChecked(stdout_saved == "true")
        self.stdoutCheck.toggled.connect(self._onStdoutToggled)
        out_row2.addWidget(self.outputFile)
        out_row2.addWidget(self.stdoutCheck)
        out_col.addWidget(out_lbl)
        out_col.addLayout(out_row2)
        fields_row.addLayout(out_col)

        fields_row.addStretch()
        cfg.addLayout(fields_row)

        # JSON row
        json_row = QHBoxLayout()
        json_row.setSpacing(6)
        json_lbl = QLabel("Test JSON Config")
        json_lbl.setStyleSheet(f"color:{TEXT_MAIN}; font-size:12px; font-weight:600; background:transparent;")
        self.jsonEditor = QTextEdit()
        self.jsonEditor.setFixedHeight(68)
        self.jsonEditor.setStyleSheet(editor_style())
        self.jsonEditor.setPlaceholderText("Paste JSON here, or use 'Load from Generator'…")
        json_row.addWidget(json_lbl)
        json_row.addWidget(self.jsonEditor, 1)

        json_btns = QVBoxLayout()
        json_btns.setSpacing(4)
        loadJsonBtn = QPushButton("Load JSON File")
        loadJsonBtn.setStyleSheet(btn_ghost())
        loadJsonBtn.clicked.connect(self.loadJson)
        fromGenBtn = QPushButton("From Generator")
        fromGenBtn.setStyleSheet(btn_ghost())
        fromGenBtn.clicked.connect(self.loadFromGenerator)
        json_btns.addWidget(loadJsonBtn)
        json_btns.addWidget(fromGenBtn)
        json_row.addLayout(json_btns)
        cfg.addLayout(json_row)

        config_card.setLayout(cfg)
        return config_card

    # ── Results header bar ────────────────────────────────────
    def _buildResultsHeader(self):
        out_header = QWidget()
        out_header.setFixedHeight(34)
        out_header.setStyleSheet(
            f"QWidget {{ background:{BG3}; border:1px solid {BORDER};"
            f"  border-bottom:none; border-radius:6px 6px 0 0; }}"
        )
        ohl = QHBoxLayout()
        ohl.setContentsMargins(12, 0, 10, 0)

        out_title = QLabel("RESULTS")
        out_title.setStyleSheet(f"color:{ACCENT}; font-size:13px; font-weight:700; background:transparent;")

        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)
        for label, key in [("All","all"),("✓ AC","ac"),("✗ WA","wa"),("⏱ TLE","tle"),("💥 RTE","rte")]:
            fb = QPushButton(label)
            fb.setFixedHeight(22)
            fb.setStyleSheet(btn_ghost())
            fb.clicked.connect(lambda _, k=key: self._filterResults(k))
            filter_row.addWidget(fb)

        clearBtn = QPushButton("Clear")
        clearBtn.setFixedHeight(22)
        clearBtn.setStyleSheet(btn_ghost())
        clearBtn.clicked.connect(self._clearResults)

        ohl.addWidget(out_title)
        ohl.addStretch()
        ohl.addLayout(filter_row)
        ohl.addWidget(clearBtn)
        out_header.setLayout(ohl)
        return out_header

    # ── Results splitter (card list + detail pane) ────────────
    def _buildResultsSplitter(self):
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setStyleSheet(
            f"QSplitter {{ background:{BG1}; border:1px solid {BORDER}; border-top:none; border-radius:0 0 6px 6px; }}"
            f"QSplitter::handle {{ background:{BORDER_BRIGHT}; width:4px; }}"
            f"QSplitter::handle:hover {{ background:{ACCENT}; }}"
        )

        # Left: card list
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setStyleSheet(f"QScrollArea {{ background:{BG1}; border:none; }}")
        self._cardContainer = QWidget()
        self._cardContainer.setStyleSheet(f"background:{BG1};")
        self._cardLayout = QVBoxLayout()
        self._cardLayout.setContentsMargins(6, 6, 6, 6)
        self._cardLayout.setSpacing(4)
        self._cardLayout.setAlignment(Qt.AlignTop)
        self._cardContainer.setLayout(self._cardLayout)
        left_scroll.setWidget(self._cardContainer)

        # Right: detail pane
        self._detailPane = QWidget()
        self._detailPane.setStyleSheet(f"background:{BG0};")
        dp_layout = QVBoxLayout()
        dp_layout.setContentsMargins(0, 0, 0, 0)
        dp_layout.setSpacing(0)

        dp_header = QWidget()
        dp_header.setFixedHeight(32)
        dp_header.setStyleSheet(f"background:{BG3};")
        dph_lay = QHBoxLayout()
        dph_lay.setContentsMargins(12, 0, 12, 0)
        self._detailTitle = QLabel("Select a test to inspect")
        self._detailTitle.setStyleSheet(f"color:{TEXT_MAIN}; font-size:12px; font-weight:700; background:transparent;")
        dph_lay.addWidget(self._detailTitle)
        dph_lay.addStretch()
        dp_header.setLayout(dph_lay)
        dp_layout.addWidget(dp_header)

        detail_splitter = QSplitter(Qt.Vertical)
        detail_splitter.setStyleSheet(
            f"QSplitter::handle {{ background:{BORDER_BRIGHT}; height:4px; }}"
            f"QSplitter::handle:hover {{ background:{ACCENT}; }}"
        )
        detail_splitter.addWidget(self._buildInputSection())
        detail_splitter.addWidget(self._buildExpectedGotSection())
        detail_splitter.setSizes([200, 200])
        dp_layout.addWidget(detail_splitter)
        self._detailPane.setLayout(dp_layout)

        self._splitter.addWidget(left_scroll)
        self._splitter.addWidget(self._detailPane)
        self._splitter.setSizes([340, 560])
        return self._splitter

    def _buildInputSection(self):
        in_wrap = QWidget()
        in_wrap.setStyleSheet(f"background:{BG0};")
        iw_lay = QVBoxLayout()
        iw_lay.setContentsMargins(0, 0, 0, 0)
        iw_lay.setSpacing(0)
        in_lbl_bar = self._sectionBar("INPUT")
        self._detailInput = QTextEdit()
        self._detailInput.setReadOnly(True)
        self._detailInput.setStyleSheet(
            f"QTextEdit {{ background:{BG0}; color:#a8c8a8; border:none;"
            f"  font-family:{FONT_MONO}; font-size:12px; padding:12px; }}"
        )
        iw_lay.addWidget(in_lbl_bar)
        iw_lay.addWidget(self._detailInput)
        in_wrap.setLayout(iw_lay)
        return in_wrap

    def _buildExpectedGotSection(self):
        eg_wrap = QWidget()
        eg_wrap.setStyleSheet(f"background:{BG0};")
        eg_lay = QVBoxLayout()
        eg_lay.setContentsMargins(0, 0, 0, 0)
        eg_lay.setSpacing(0)
        eg_lbl_bar = self._sectionBar("EXPECTED  vs  GOT")
        eg_cols = QSplitter(Qt.Horizontal)
        eg_cols.setStyleSheet(f"QSplitter::handle {{ background:{BORDER}; width:2px; }}")
        self._detailExpected = QTextEdit()
        self._detailExpected.setReadOnly(True)
        self._detailExpected.setStyleSheet(
            f"QTextEdit {{ background:{BG0}; color:{GREEN}; border:none;"
            f"  font-family:{FONT_MONO}; font-size:12px; padding:8px; }}"
        )
        self._detailGot = QTextEdit()
        self._detailGot.setReadOnly(True)
        self._detailGot.setStyleSheet(
            f"QTextEdit {{ background:{BG0}; color:{RED}; border:none;"
            f"  font-family:{FONT_MONO}; font-size:12px; padding:8px; }}"
        )
        eg_cols.addWidget(self._detailExpected)
        eg_cols.addWidget(self._detailGot)
        eg_lay.addWidget(eg_lbl_bar)
        eg_lay.addWidget(eg_cols)
        
        # AI Analysis button
        ai_btn_row = QHBoxLayout()
        ai_btn_row.setContentsMargins(0, 8, 0, 0)
        ai_btn_row.setSpacing(8)
        self.analyzeBtn = QPushButton("🤖 Analyse with AI")
        self.analyzeBtn.setStyleSheet(btn_primary())
        self.analyzeBtn.setFixedHeight(32)
        self.analyzeBtn.setEnabled(False)
        self.analyzeBtn.clicked.connect(self._analyzeWithAI)
        ai_btn_row.addStretch()
        ai_btn_row.addWidget(self.analyzeBtn)
        eg_lay.addLayout(ai_btn_row)
        
        eg_wrap.setLayout(eg_lay)
        return eg_wrap

    def _sectionBar(self, text):
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setStyleSheet(f"background:{BG2};")
        lay = QHBoxLayout()
        lay.setContentsMargins(10, 0, 10, 0)
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; font-weight:700; background:transparent;")
        lay.addWidget(lbl)
        bar.setLayout(lay)
        return bar

    # ── I/O toggles ───────────────────────────────────────────
    def _onStdinToggled(self, checked):
        self.inputFile.setEnabled(not checked)
        save("judge_stdin", "true" if checked else "false")

    def _onStdoutToggled(self, checked):
        self.outputFile.setEnabled(not checked)
        save("judge_stdout", "true" if checked else "false")

    # ── JSON loading ──────────────────────────────────────────
    def loadJson(self):
        file, _ = QFileDialog.getOpenFileName(self, "Load JSON", "", "*.json")
        if file:
            with open(file, "r", encoding="utf-8") as f:
                self.jsonEditor.setText(f.read())

    def loadFromGenerator(self):
        gen_output = self.parent_app.genTab.output.toPlainText()
        if not gen_output.strip():
            self._addErrorCard("Generator has no JSON yet — go to Generator tab and click Build JSON first.")
            return
        self.jsonEditor.setText(gen_output)

    # ── Run tests ─────────────────────────────────────────────
    def runTests(self):
        user_code   = self.userPanel.code()
        answer_code = self.ansPanel.code()
        json_text   = self.jsonEditor.toPlainText()

        if not user_code.strip():
            self._addErrorCard("⚠  No user code provided.")
            return
        if not answer_code.strip():
            self._addErrorCard("⚠  No answer code provided.")
            return
        try:
            timeLimit = float(self.timeInput.text())
        except (ValueError, TypeError):
            self._addErrorCard("⚠  Invalid time limit.")
            return
        try:
            jsonData = json.loads(json_text)
        except Exception:
            self._addErrorCard("⚠  Invalid JSON config.")
            return

        input_file  = None if self.stdinCheck.isChecked()  else (self.inputFile.text().strip()  or None)
        output_file = None if self.stdoutCheck.isChecked() else (self.outputFile.text().strip() or "output.out")

        self._clearResults()
        self.runBtn.setEnabled(False)
        self.statusLabel.setText("Running…")
        self.resultSummary.setText("")
        self.progressBar.setValue(0)
        self._correct = 0
        self._total   = 0

        self.worker = TestWorker(
            user_code, answer_code, jsonData, timeLimit,
            self.userPanel.lang(), self.ansPanel.lang(),
            input_file, output_file,
        )
        self.worker.progress.connect(self.progressBar.setValue)
        self.worker.new_result.connect(self._addResultCard)
        self.worker.finished.connect(self._onFinished)
        self.worker.start()

    # ── Card system ───────────────────────────────────────────
    VERDICT_STYLE = {
        "AC":  (GREEN,  GREEN_DIM,  "✓"),
        "WA":  (RED,    RED_DIM,    "✗"),
        "TLE": (AMBER,  AMBER_DIM,  "⏱"),
        "RTE": (RED,    RED_DIM,    "💥"),
        "JE":  (AMBER,  AMBER_DIM,  "⚙"),
    }

    def _addResultCard(self, result: dict):
        self._all_results.append(result)
        self._total += 1
        if result["verdict"] == "AC":
            self._correct += 1
        pct   = int(self._correct * 100 / self._total) if self._total else 0
        color = GREEN if self._correct == self._total else (AMBER if self._correct > 0 else RED)
        self.resultSummary.setText(f"{self._correct}/{self._total}  ({pct}%)")
        self.resultSummary.setStyleSheet(
            f"color:{color}; font-size:13px; font-weight:700; background:transparent;"
        )
        self._buildCard(result)

    def _buildCard(self, result: dict):
        v = result["verdict"]
        fg, bg, icon = self.VERDICT_STYLE.get(v, (TEXT_DIM, BG2, "?"))

        card = QWidget()
        card.setObjectName("resultCard")
        card.setCursor(Qt.PointingHandCursor)
        card.setFixedHeight(44)
        card.setStyleSheet(
            f"QWidget#resultCard {{ background:{bg}; border:1px solid {fg}40;"
            f"  border-left:4px solid {fg}; border-radius:5px; }}"
            f"QWidget#resultCard:hover {{ background:{fg}22; border-color:{fg}; }}"
        )
        hl = QHBoxLayout()
        hl.setContentsMargins(10, 0, 10, 0)
        hl.setSpacing(10)

        badge = QLabel(f"{icon} {v}")
        badge.setFixedWidth(60)
        badge.setStyleSheet(
            f"color:{fg}; font-size:13px; font-weight:800;"
            f"background:transparent; border:none; font-family:{FONT_MONO};"
        )

        loc = QLabel(f"Task {result['task']}  ·  Test {result['index']}")
        loc.setStyleSheet(f"color:{TEXT_MAIN}; font-size:12px; background:transparent; border:none;")

        exp_short = " ".join(result["answer"][:4])
        got_short = " ".join(result["user"][:4])
        if len(result["answer"]) > 4: exp_short += " …"
        if len(result["user"])   > 4: got_short += " …"

        if v == "AC":
            preview = QLabel(exp_short)
            preview.setStyleSheet(f"color:{GREEN}; font-size:11px; font-family:{FONT_MONO}; background:transparent; border:none;")
        else:
            preview = QLabel(f"exp: {exp_short}   got: {got_short}")
            preview.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; font-family:{FONT_MONO}; background:transparent; border:none;")

        hl.addWidget(badge)
        hl.addWidget(loc)
        hl.addStretch()
        hl.addWidget(preview)
        card.setLayout(hl)
        card.mousePressEvent = lambda e, r=result: self._showDetail(r)
        self._cardLayout.addWidget(card)

    def _showDetail(self, result: dict):
        v = result["verdict"]
        fg, _, icon = self.VERDICT_STYLE.get(v, (TEXT_DIM, BG2, "?"))
        self._detailTitle.setText(f"{icon} {v}  —  Task {result['task']}, Test {result['index']}")
        self._detailTitle.setStyleSheet(
            f"color:{fg}; font-size:13px; font-weight:800; background:transparent;"
        )
        self._detailInput.setPlainText(result.get("input", ""))
        self._detailExpected.setPlainText("\n".join(result["answer"]))
        self._detailGot.setPlainText("\n".join(result["user"]))
        got_col = GREEN if v == "AC" else RED
        self._detailGot.setStyleSheet(
            f"QTextEdit {{ background:{BG0}; color:{got_col}; border:none;"
            f"  font-family:{FONT_MONO}; font-size:12px; padding:8px; }}"
        )

    def _clearResults(self):
        self._all_results = []
        self._correct = 0
        self._total   = 0
        while self._cardLayout.count():
            item = self._cardLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._detailTitle.setText("Select a test to inspect")
        self._detailTitle.setStyleSheet(
            f"color:{TEXT_MAIN}; font-size:12px; font-weight:700; background:transparent;"
        )
        self._detailInput.clear()
        self._detailExpected.clear()
        self._detailGot.clear()

    def _filterResults(self, key: str):
        while self._cardLayout.count():
            item = self._cardLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for r in self._all_results:
            if key == "all" or r["verdict"].lower() == key:
                self._buildCard(r)

    def _addErrorCard(self, msg: str):
        lbl = QLabel(msg)
        lbl.setStyleSheet(
            f"color:{AMBER}; background:{AMBER_DIM}; border:1px solid {AMBER}40;"
            f"border-radius:5px; padding:8px 12px; font-size:12px;"
        )
        lbl.setWordWrap(True)
        self._cardLayout.addWidget(lbl)

    def _onFinished(self):
        self.runBtn.setEnabled(True)
        total   = self._total
        correct = self._correct
        color   = GREEN if correct == total else (AMBER if correct > 0 else RED)
        self.statusLabel.setText("Done")
        self.resultSummary.setText(
            f"{correct}/{total}  ({int(correct*100/total) if total else 0}%)"
        )
        self.resultSummary.setStyleSheet(
            f"color:{color}; font-size:13px; font-weight:700; background:transparent;"
        )

    # ── AI Analysis ─────────────────────────────────────────────
    def _analyzeWithAI(self):
        if not hasattr(self, '_current_result'):
            return
        
        result = self._current_result
        if result["verdict"] == "AC":
            return
        
        dialog = AIAnalysisDialog(self, result, self.userPanel.code(), self.ansPanel.code(), self.userPanel.lang())
        dialog.exec()

    def _openAIConfig(self):
        dialog = AIConfigDialog(self)
        dialog.exec()

    def _generateTestJSON(self):
        """Generate test JSON blueprint using AI"""
        dialog = AIGenerationDialog(self, "json", self.userPanel.code(), self.ansPanel.code(), self.userPanel.lang())
        dialog.exec()

    def _generateAnswerCode(self):
        """Generate answer code using AI"""
        dialog = AIGenerationDialog(self, "answer", self.userPanel.code(), self.ansPanel.code(), self.userPanel.lang())
        dialog.exec()

    def _showDetail(self, result: dict):
        self._current_result = result
        v = result["verdict"]
        fg, _, icon = self.VERDICT_STYLE.get(v, (TEXT_DIM, BG2, "?"))
        self._detailTitle.setText(f"{icon} {v}  —  Task {result['task']}, Test {result['index']}")
        self._detailTitle.setStyleSheet(
            f"color:{fg}; font-size:13px; font-weight:800; background:transparent;"
        )
        self._detailInput.setPlainText(result.get("input", ""))
        self._detailExpected.setPlainText("\n".join(result["answer"]))
        self._detailGot.setPlainText("\n".join(result["user"]))
        got_col = GREEN if v == "AC" else RED
        self._detailGot.setStyleSheet(
            f"QTextEdit {{ background:{BG0}; color:{got_col}; border:none;"
            f"  font-family:{FONT_MONO}; font-size:12px; padding:8px; }}"
        )
        self.analyzeBtn.setEnabled(v != "AC")

# ─────────────────────────────────────────────────────────────────────────────
# REPLACE the AIAnalysisDialog and AIConfigDialog classes at the bottom of
# your judge_tab.py with these versions.
#
# Changes:
#   - AIAnalysisDialog now streams the AI response token-by-token (no more
#     waiting for the full response before seeing anything)
#   - AIConfigDialog now matches the provider keys used by ai_worker.py
# ─────────────────────────────────────────────────────────────────────────────

from PySide6.QtGui import QTextCursor


# ─────────────────────────────────────────────────────────────
# Replace AIAnalysisDialog and AIConfigDialog at the bottom of
# judge_tab.py with these two classes.
#
# Also add this import near the top of judge_tab.py:
#   from PySide6.QtGui import QTextCursor
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# Replace AIAnalysisDialog at the bottom of judge_tab.py
# with this class. Also delete AIConfigDialog entirely.
#
# Add this import near the top of judge_tab.py:
#   from PySide6.QtGui import QTextCursor
# ─────────────────────────────────────────────────────────────


class AIAnalysisDialog(QDialog):
    def __init__(self, parent, result, user_code, answer_code, language):
        super().__init__(parent)
        self.setWindowTitle("AI Debug Analysis")
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{BG1}; }}")
        self.resize(700, 580)
        self._result      = result
        self._user_code   = user_code
        self._answer_code = answer_code
        self._language    = language

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        v    = result["verdict"]
        fg   = RED if v in ("WA", "RTE") else AMBER
        icon = {"WA": "✗", "RTE": "💥", "TLE": "⏱"}.get(v, "?")
        title = QLabel(
            f"🤖  AI Analysis — {icon} {v}  ·  Task {result['task']}, Test {result['index']}"
        )
        title.setStyleSheet(
            f"color:{fg}; font-size:13px; font-weight:800; background:transparent;"
        )
        layout.addWidget(title)

        # Problem statement
        ps_lbl = QLabel("Problem statement  (optional but recommended — paste it for better analysis)")
        ps_lbl.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:11px; font-weight:600; background:transparent;"
        )
        layout.addWidget(ps_lbl)
        self._stmt = QTextEdit()
        self._stmt.setFixedHeight(90)
        self._stmt.setPlaceholderText("Paste the problem statement here…")
        self._stmt.setStyleSheet(editor_style())
        self._stmt.setText(load("ai_problem_statement", ""))
        layout.addWidget(self._stmt)

        # Streaming output
        out_lbl = QLabel("Analysis")
        out_lbl.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:11px; font-weight:600; background:transparent;"
        )
        layout.addWidget(out_lbl)
        self._out = QTextEdit()
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("Click Analyse to start…")
        self._out.setStyleSheet(
            f"QTextEdit {{ background:{BG0}; color:{TEXT_MAIN};"
            f"  border:1px solid {BORDER}; border-radius:8px;"
            f"  font-family:{FONT_UI}; font-size:13px; padding:12px; }}"
            f"QTextEdit {{ selection-background-color:{ACCENT}; selection-color:#fff; }}"
        )
        layout.addWidget(self._out, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn = QPushButton("▶  Analyse")
        self._btn.setStyleSheet(btn_primary())
        self._btn.clicked.connect(self._start)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(btn_ghost())
        close_btn.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(self._btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _start(self):
        from ai_worker import AIWorker
        from PySide6.QtGui import QTextCursor

        stmt = self._stmt.toPlainText().strip()
        save("ai_problem_statement", stmt)
        self._btn.setEnabled(False)
        self._btn.setText("Analysing…")
        self._out.clear()

        self._worker = AIWorker(
            user_code         = self._user_code,
            answer_code       = self._answer_code,
            test_input        = self._result.get("input", ""),
            expected          = "\n".join(self._result.get("answer", [])),
            got               = "\n".join(self._result.get("user",   [])),
            verdict           = self._result["verdict"],
            task              = self._result["task"],
            index             = self._result["index"],
            language          = self._language,
            problem_statement = stmt,
            output_mode       = "analysis",
        )
        self._worker.chunk.connect(self._stream_token)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stream_token(self, token: str):
        from PySide6.QtGui import QTextCursor
        c = self._out.textCursor()
        c.movePosition(QTextCursor.End)
        c.insertText(token)
        self._out.setTextCursor(c)
        self._out.ensureCursorVisible()

    def _apply_json_highlighting(self, text: str):
        """Apply basic JSON syntax highlighting"""
        try:
            import json
            data = json.loads(text)
            formatted = json.dumps(data, indent=2)
            
            # Simple syntax highlighting
            highlighted = formatted
            highlighted = highlighted.replace('"', '<span style="color:#a5d6ff;">"</span>')
            highlighted = highlighted.replace(':', '<span style="color:#ff7b72;">:</span>')
            highlighted = highlighted.replace(',', '<span style="color:#8b949e;">,</span>')
            highlighted = highlighted.replace('{', '<span style="color:#ff7b72;">{</span>')
            highlighted = highlighted.replace('}', '<span style="color:#ff7b72;">}</span>')
            highlighted = highlighted.replace('[', '<span style="color:#ff7b72;">[</span>')
            highlighted = highlighted.replace(']', '<span style="color:#ff7b72;">]</span>')
            
            return highlighted
        except:
            return text

    def _on_done(self):
        self._btn.setEnabled(True)
        self._btn.setText("▶  Analyse again")

    def _on_error(self, msg: str):
        self._out.setPlainText(f"Error:\n\n{msg}")
        self._btn.setEnabled(True)
        self._btn.setText("▶  Analyse")


class AIGenerationDialog(QDialog):
    def __init__(self, parent, mode, user_code, answer_code, language):
        super().__init__(parent)
        self.mode = mode
        self.user_code = user_code
        self.answer_code = answer_code
        self.language = language
        
        if mode == "json":
            self.setWindowTitle("Generate Test JSON")
        else:
            self.setWindowTitle("Generate Answer Code")
        
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{BG1}; }}")
        self.resize(700, 500)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel(f"🤖 AI Generation - {mode.upper()}")
        title.setStyleSheet(f"color:{ACCENT}; font-size:14px; font-weight:700; background:transparent;")
        layout.addWidget(title)

        # Problem statement field
        ps_label = QLabel("Problem Statement (optional but recommended):")
        ps_label.setStyleSheet(f"color:{TEXT_MAIN}; font-size:12px; font-weight:600; background:transparent;")
        layout.addWidget(ps_label)
        
        self.problemStatement = QTextEdit()
        self.problemStatement.setMaximumHeight(100)
        self.problemStatement.setPlaceholderText("Paste the problem statement here for better generation...")
        self.problemStatement.setStyleSheet(editor_style())
        self.problemStatement.setText(load("ai_problem_statement", ""))
        layout.addWidget(self.problemStatement)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Click 'Generate' to start...")
        self.output.setStyleSheet(editor_style())
        layout.addWidget(self.output, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.generateBtn = QPushButton("Generate")
        self.generateBtn.setStyleSheet(btn_primary())
        self.generateBtn.clicked.connect(self._startGeneration)
        self.acceptBtn = QPushButton("✓ Accept")
        self.acceptBtn.setStyleSheet(btn_green())
        self.acceptBtn.setEnabled(False)
        self.acceptBtn.clicked.connect(self._acceptContent)
        closeBtn = QPushButton("Close")
        closeBtn.setStyleSheet(btn_ghost())
        closeBtn.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(self.generateBtn)
        btn_row.addWidget(self.acceptBtn)
        btn_row.addWidget(closeBtn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def _startGeneration(self):
        self.generateBtn.setEnabled(False)
        self.generateBtn.setText("Generating...")
        self.output.clear()
        
        problem_statement = self.problemStatement.toPlainText().strip()
        save("ai_problem_statement", problem_statement)
        
        self.worker = AIWorker(
            user_code=self.user_code,
            answer_code=self.answer_code,
            test_input="",
            expected="",
            got="",
            verdict="",
            task=1,
            index=1,
            language=self.language,
            problem_statement=problem_statement,
            output_mode=self.mode
        )
        self.worker.chunk.connect(self._streamToken)
        self.worker.finished.connect(self._onDone)
        self.worker.error.connect(self._onError)
        self.worker.start()

    def _streamToken(self, token):
        from PySide6.QtGui import QTextCursor
        c = self.output.textCursor()
        c.movePosition(QTextCursor.End)
        c.insertText(token)
        self.output.setTextCursor(c)
        self.output.ensureCursorVisible()

    def _onDone(self):
        self.generateBtn.setEnabled(True)
        self.generateBtn.setText("Generate")
        self.acceptBtn.setEnabled(True)
        
        # Remove markdown code blocks
        content = self.output.toPlainText()
        content = re.sub(r'```[\w]*\n?', '', content)
        content = re.sub(r'```', '', content)
        self.output.setPlainText(content)

    def _onError(self, error_msg):
        self.output.setPlainText(f"Error: {error_msg}")
        self.generateBtn.setEnabled(True)
        self.generateBtn.setText("Generate")

    def _applyJsonHighlighting(self, text):
        try:
            import json
            data = json.loads(text)
            formatted = json.dumps(data, indent=2)
            highlighted = formatted
            highlighted = highlighted.replace('"', '<span style="color:#a5d6ff;">"</span>')
            highlighted = highlighted.replace(':', '<span style="color:#ff7b72;">:</span>')
            highlighted = highlighted.replace(',', '<span style="color:#8b949e;">,</span>')
            highlighted = highlighted.replace('{', '<span style="color:#ff7b72;">{</span>')
            highlighted = highlighted.replace('}', '<span style="color:#ff7b72;">}</span>')
            highlighted = highlighted.replace('[', '<span style="color:#ff7b72;">[</span>')
            highlighted = highlighted.replace(']', '<span style="color:#ff7b72;">]</span>')
            return highlighted
        except:
            return text

    def _acceptContent(self):
        """Apply generated content to the appropriate place"""
        content = self.output.toPlainText()
        if self.mode == "json":
            # Apply to JSON editor in parent judge tab
            self.parent().jsonEditor.setText(content)
        elif self.mode == "answer":
            # Apply to answer code panel
            self.parent().ansPanel.editor.setText(content)
        self.accept()


class AIConfigDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("AI Configuration")
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{BG1}; }}")
        self.setFixedWidth(500)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("AI Debug Setup")
        title.setStyleSheet(f"color:{ACCENT}; font-size:14px; font-weight:700; background:transparent;")
        layout.addWidget(title)

        # Simple mode selector
        mode_lbl = QLabel("Mode:")
        mode_lbl.setStyleSheet(f"color:{TEXT_MAIN}; font-size:12px; font-weight:600; background:transparent;")
        layout.addWidget(mode_lbl)
        
        self.modeBox = QComboBox()
        self.modeBox.addItems(["basic (no setup)", "groq (free API)", "custom API"])
        self.modeBox.setStyleSheet(line_edit_style())
        self.modeBox.currentTextChanged.connect(self._onModeChanged)
        layout.addWidget(self.modeBox)


        # Groq settings (hidden by default)
        self.groq_group = QWidget()
        groq_layout = QVBoxLayout()
        groq_layout.setSpacing(6)
        
        groq_key_lbl = QLabel("API Key:")
        groq_key_lbl.setStyleSheet(f"color:{TEXT_MAIN}; font-size:11px; font-weight:600; background:transparent;")
        self.groqKeyEdit = QLineEdit()
        self.groqKeyEdit.setEchoMode(QLineEdit.Password)
        self.groqKeyEdit.setPlaceholderText("gsk_...")
        self.groqKeyEdit.setStyleSheet(line_edit_style())
        self.groqKeyEdit.setText(load("groq_key", ""))
        
        groq_model_lbl = QLabel("Model:")
        groq_model_lbl.setStyleSheet(f"color:{TEXT_MAIN}; font-size:11px; font-weight:600; background:transparent;")
        self.groqModelEdit = QLineEdit()
        self.groqModelEdit.setPlaceholderText("llama-3.3-70b-versatile")
        self.groqModelEdit.setStyleSheet(line_edit_style())
        self.groqModelEdit.setText(load("groq_model", "llama-3.3-70b-versatile"))
        
        groq_layout.addWidget(groq_key_lbl)
        groq_layout.addWidget(self.groqKeyEdit)
        groq_layout.addWidget(groq_model_lbl)
        groq_layout.addWidget(self.groqModelEdit)
        
        # Get API key link
        groq_link = QLabel('<a href="https://console.groq.com/keys">Get free Groq API key</a>')
        groq_link.setStyleSheet(f"color:{ACCENT}; font-size:10px; background:transparent;")
        groq_link.setOpenExternalLinks(True)
        groq_layout.addWidget(groq_link)
        
        self.groq_group.setLayout(groq_layout)
        self.groq_group.setVisible(False)
        layout.addWidget(self.groq_group)

        # Custom API settings (hidden by default)
        self.api_group = QWidget()
        api_layout = QVBoxLayout()
        api_layout.setSpacing(6)
        
        api_url_lbl = QLabel("API URL:")
        api_url_lbl.setStyleSheet(f"color:{TEXT_MAIN}; font-size:11px; font-weight:600; background:transparent;")
        self.apiUrlEdit = QLineEdit()
        self.apiUrlEdit.setPlaceholderText("https://api.example.com/v1/chat")
        self.apiUrlEdit.setStyleSheet(line_edit_style())
        self.apiUrlEdit.setText(load("custom_api_url", ""))
        
        api_key_lbl = QLabel("API Key:")
        api_key_lbl.setStyleSheet(f"color:{TEXT_MAIN}; font-size:11px; font-weight:600; background:transparent;")
        self.apiKeyEdit = QLineEdit()
        self.apiKeyEdit.setEchoMode(QLineEdit.Password)
        self.apiKeyEdit.setPlaceholderText("your-api-key")
        self.apiKeyEdit.setStyleSheet(line_edit_style())
        self.apiKeyEdit.setText(load("custom_api_key", ""))
        
        api_layout.addWidget(api_url_lbl)
        api_layout.addWidget(self.apiUrlEdit)
        api_layout.addWidget(api_key_lbl)
        api_layout.addWidget(self.apiKeyEdit)
        self.api_group.setLayout(api_layout)
        self.api_group.setVisible(False)
        layout.addWidget(self.api_group)

        # Info text
        info = QLabel(
            "💡 Basic mode: Simple pattern matching, works immediately.\n"
            "   Groq: Free fast AI API, get key at console.groq.com/keys\n"
            "   Custom API: For advanced users with API access"
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{TEXT_HINT}; font-size:10px; background:transparent;")
        layout.addWidget(info)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(btn_primary())
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(btn_ghost())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        
        # Set current mode
        current_mode = load("ai_mode", "basic")
        self.modeBox.setCurrentText(current_mode)
        self._onModeChanged(current_mode)

    def _onModeChanged(self, mode):
        self.groq_group.setVisible(mode == "groq (free API)")
        self.api_group.setVisible(mode == "custom API")

    def _save(self):
        mode = self.modeBox.currentText()
        save("ai_mode", mode)
        save("groq_key", self.groqKeyEdit.text())
        save("groq_model", self.groqModelEdit.text())
        save("custom_api_url", self.apiUrlEdit.text())
        save("custom_api_key", self.apiKeyEdit.text())
        self.accept()