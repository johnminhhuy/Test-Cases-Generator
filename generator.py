# generator_tab.py — LoopDialog and GeneratorTab

import re
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QLineEdit, QComboBox, QFileDialog,
    QSpinBox, QScrollArea, QFrame, QListWidget, QDialog,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QSyntaxHighlighter

from theme import (
    BG0, BG1, BG2, BG3, BORDER, BORDER_BRIGHT,
    TEXT_MAIN, TEXT_DIM, TEXT_HINT,
    ACCENT, ACCENT_DIM, GREEN, RED,
    FONT_MONO, FONT_UI,
    palette_for,
    editor_style, line_edit_style, section_label_style,
    btn_primary, btn_ghost, btn_danger, btn_green,
)
from highlighters import TemplateHighlighter
from widgets import save, load

import testUtils


# ── Template editor with click-to-highlight ───────────────────
class TemplateEditor(QTextEdit):
    tokenClicked = Signal(str)

    def __init__(self):
        super().__init__()
        self._highlighter = TemplateHighlighter(self.document())
        self.setAcceptRichText(False)
        self.setStyleSheet(editor_style())

    def set_variables(self, variables: dict, name_to_index: dict):
        self._highlighter.set_variables(variables, name_to_index)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        cursor = self.cursorForPosition(event.position().toPoint())
        pos    = cursor.positionInBlock()
        line   = cursor.block().text()
        for m in re.finditer(r'\{(\w+)\}', line):
            if m.start() <= pos <= m.end():
                self.tokenClicked.emit(m.group(1))
                return


# ── Loop insertion dialog ─────────────────────────────────────
class LoopDialog(QDialog):
    def __init__(self, parent, var_names):
        super().__init__(parent)
        self.setWindowTitle("Insert Loop")
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{BG1}; }}")
        self.setFixedWidth(380)
        self.result_value = None

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Insert @count{ } Loop")
        title.setStyleSheet(f"color:{ACCENT}; font-size:14px; font-weight:700; background:transparent;")
        layout.addWidget(title)

        desc = QLabel(
            "Repeat an inner block a number of times.\n"
            "Count can be a fixed number or a variable."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; background:transparent;")
        layout.addWidget(desc)

        if var_names:
            var_lbl = QLabel("Quick insert from variables:")
            var_lbl.setStyleSheet(f"color:{TEXT_HINT}; font-size:10px; background:transparent;")
            layout.addWidget(var_lbl)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(6)
            for i, name in enumerate(var_names[:6]):
                bg, fg, bd = palette_for(i)
                b = QPushButton(name)
                b.setStyleSheet(
                    f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {bd};"
                    f"  border-radius:10px; padding:3px 10px; font-size:11px; font-family:{FONT_MONO}; font-weight:700; }}"
                    f"QPushButton:hover {{ background:{bd}; color:#fff; }}"
                )
                b.clicked.connect(lambda _, n=name: self._select(n))
                btn_row.addWidget(b)
            btn_row.addStretch()
            layout.addLayout(btn_row)

        manual_lbl = QLabel("Or type a count:")
        manual_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; background:transparent;")
        layout.addWidget(manual_lbl)

        entry_row = QHBoxLayout()
        self.countEdit = QLineEdit()
        self.countEdit.setPlaceholderText("e.g.  n  or  5")
        self.countEdit.setStyleSheet(line_edit_style())
        entry_row.addWidget(self.countEdit)

        ok_btn = QPushButton("Insert")
        ok_btn.setStyleSheet(btn_primary())
        ok_btn.clicked.connect(self._ok)
        entry_row.addWidget(ok_btn)
        layout.addLayout(entry_row)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(btn_ghost())
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        self.setLayout(layout)

    def _select(self, name):
        self.result_value = name
        self.accept()

    def _ok(self):
        val = self.countEdit.text().strip()
        if val:
            self.result_value = val
            self.accept()


# ── Generator Tab ─────────────────────────────────────────────
class GeneratorTab(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout()
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        split = QHBoxLayout()
        split.setSpacing(8)
        split.addLayout(self._buildLeft(), 3)
        split.addLayout(self._buildRight(), 2)
        root.addLayout(split)
        self.setLayout(root)

        self.subtasks      = []
        self.current_index = -1
        self._name_to_index: dict[str, int] = {}
        self._loadMemory()

    # ── Build left column ─────────────────────────────────────
    def _buildLeft(self):
        left = QVBoxLayout()
        left.setSpacing(6)

        # Step 1 — Subtasks
        step1 = self._stepCard("1  Subtasks")
        s1 = step1.layout()

        self.subtaskList = QListWidget()
        self.subtaskList.setFixedHeight(90)
        self.subtaskList.currentRowChanged.connect(self.switchSubtask)
        s1.addWidget(self.subtaskList)

        s1_btns = QHBoxLayout()
        s1_btns.setSpacing(4)
        addSubBtn = QPushButton("+ Add")
        addSubBtn.setStyleSheet(btn_ghost())
        addSubBtn.clicked.connect(self.addSubtask)
        self.removeSubBtn = QPushButton("Remove")
        self.removeSubBtn.setStyleSheet(btn_danger())
        self.removeSubBtn.clicked.connect(self.removeSubtask)
        tc_lbl = QLabel("Tests:")
        tc_lbl.setStyleSheet(f"color:{TEXT_MAIN}; font-size:12px; font-weight:600; background:transparent;")
        self.testCountInput = QSpinBox()
        self.testCountInput.setRange(1, 100000)
        self.testCountInput.setValue(10)
        self.testCountInput.setFixedWidth(70)
        self.testCountInput.valueChanged.connect(self.saveTestCount)
        s1_btns.addWidget(addSubBtn)
        s1_btns.addWidget(self.removeSubBtn)
        s1_btns.addStretch()
        s1_btns.addWidget(tc_lbl)
        s1_btns.addWidget(self.testCountInput)
        s1.addLayout(s1_btns)
        left.addWidget(step1)

        # Step 2 — Variables
        step2 = self._stepCard("2  Variables")
        s2 = step2.layout()
        self.varContainer = QWidget()
        self.varLayout = QVBoxLayout()
        self.varLayout.setSpacing(3)
        self.varLayout.setContentsMargins(0, 0, 0, 0)
        self.varLayout.setAlignment(Qt.AlignTop)
        self.varContainer.setLayout(self.varLayout)
        varScroll = QScrollArea()
        varScroll.setWidgetResizable(True)
        varScroll.setFrameShape(QFrame.NoFrame)
        varScroll.setWidget(self.varContainer)
        varScroll.setFixedHeight(150)
        varScroll.setStyleSheet(f"QScrollArea {{ background:{BG0}; border:none; }}")
        s2.addWidget(varScroll)
        self._varScroll = varScroll
        addVarBtn = QPushButton("+ Add Variable")
        addVarBtn.setStyleSheet(btn_ghost())
        addVarBtn.clicked.connect(self.addVariableRow)
        s2.addWidget(addVarBtn)
        left.addWidget(step2)

        # Step 3 — Template
        step3 = self._stepCard("3  Template")
        s3 = step3.layout()
        self.tokenBarWidget = QWidget()
        self.tokenBarWidget.setStyleSheet("background:transparent;")
        self.tokenBarLayout = QHBoxLayout()
        self.tokenBarLayout.setContentsMargins(0, 0, 0, 2)
        self.tokenBarLayout.setSpacing(4)
        self.tokenBarWidget.setLayout(self.tokenBarLayout)
        s3.addWidget(self.tokenBarWidget)
        self.editor = TemplateEditor()
        self.editor.setPlaceholderText(
            "Example:\n{n}\n@n{ {a} }\n\n"
            "• {varname} inserts a variable\n"
            "• @n{ ... } repeats n times"
        )
        self.editor.tokenClicked.connect(self._onTokenClicked)
        s3.addWidget(self.editor)
        loopBtn = QPushButton("⟳  Insert Loop")
        loopBtn.setStyleSheet(
            f"QPushButton {{ background:#0d2a18; color:#5bf59a;"
            f"  border:1px solid #2a7a4a; border-radius:5px;"
            f"  font-family:{FONT_UI}; font-size:12px; font-weight:600; padding:5px 12px; }}"
            f"QPushButton:hover {{ background:#1a5a30; border-color:#5bf59a; }}"
        )
        loopBtn.clicked.connect(self.insertLoop)
        s3.addWidget(loopBtn)
        left.addWidget(step3, 1)

        # Constraints
        self.constraintEditor = QTextEdit()
        self.constraintEditor.setPlaceholderText("Constraints (optional): 1 ≤ n ≤ 10⁵  ...")
        self.constraintEditor.setFixedHeight(54)
        self.constraintEditor.setStyleSheet(editor_style())
        self.constraintEditor.textChanged.connect(self._onConstraintChanged)
        left.addWidget(self.constraintEditor)

        return left

    # ── Build right column ────────────────────────────────────
    def _buildRight(self):
        right = QVBoxLayout()
        right.setSpacing(6)

        # Preview
        prevCard = self._stepCard("Preview")
        pc = prevCard.layout()
        self.previewBox = QTextEdit()
        self.previewBox.setReadOnly(True)
        self.previewBox.setFixedHeight(120)
        self.previewBox.setStyleSheet(
            f"QTextEdit {{ background:{BG0}; border:none;"
            f"  color:{GREEN}; font-family:{FONT_MONO}; font-size:12px; padding:6px; }}"
        )
        pc.addWidget(self.previewBox)
        previewBtn = QPushButton("↻ Refresh")
        previewBtn.setStyleSheet(btn_ghost())
        previewBtn.clicked.connect(self.previewTest)
        pc.addWidget(previewBtn)
        right.addWidget(prevCard)

        # JSON output
        jsonCard = self._stepCard("Generated JSON")
        jc = jsonCard.layout()
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet(editor_style())
        jc.addWidget(self.output)
        right.addWidget(jsonCard, 1)

        # Action buttons
        for label, slot, tip, style in [
            ("Build JSON",       self.generateJson,  "Compile subtasks → JSON", btn_primary()),
            ("Save JSON",        self.saveJson,       "Save JSON to file",       btn_ghost()),
            ("Load JSON",        self.loadJson,       "Load JSON from file",     btn_ghost()),
            ("Send to Judge ▶",  self.sendToJudge,    "Send to Judge tab",       btn_green()),
        ]:
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.setStyleSheet(style)
            btn.clicked.connect(slot)
            right.addWidget(btn)

        clearMemBtn = QPushButton("Clear Saved State")
        clearMemBtn.setToolTip("Wipe all saved subtasks from memory")
        clearMemBtn.setStyleSheet(btn_danger())
        clearMemBtn.clicked.connect(self._clearMemory)
        right.addWidget(clearMemBtn)

        return right

    # ── Step card helper ──────────────────────────────────────
    def _stepCard(self, title):
        card = QWidget()
        card.setStyleSheet(
            f"QWidget {{ background:{BG2}; border:1px solid {BORDER}; border-radius:6px; }}"
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color:{ACCENT}; font-size:12px; font-weight:800; background:transparent;")
        layout.addWidget(lbl)
        card.setLayout(layout)
        return card

    # ── Persistent memory ─────────────────────────────────────
    def _saveMemory(self):
        self.saveCurrent()
        save("gen_subtasks", json.dumps(self.subtasks))

    def _loadMemory(self):
        raw = load("gen_subtasks", None)
        if raw:
            try:
                saved = json.loads(raw)
                if isinstance(saved, list) and len(saved) > 0:
                    self.subtasks = saved
                    self.subtaskList.clear()
                    for i in range(len(self.subtasks)):
                        self.subtaskList.addItem(f"Subtask {i + 1}")
                    self.current_index = -1
                    self.subtaskList.setCurrentRow(0)
                    return
            except Exception:
                pass
        self.addSubtask()

    # ── Helpers ───────────────────────────────────────────────
    def _insertAtCursor(self, text):
        self.editor.textCursor().insertText(text)
        self.editor.setFocus()

    def _onTokenClicked(self, name):
        for i in range(self.varLayout.count()):
            item = self.varLayout.itemAt(i)
            if not item or not item.widget():
                continue
            row = item.widget()
            if row._fields[0].text().strip() == name:
                self._varScroll.ensureWidgetVisible(row)
                self._flashRow(row, i)
                return

    def _flashRow(self, row, index):
        bg, fg, _ = palette_for(index)
        orig = row.styleSheet()
        row.setStyleSheet(
            f"QWidget#varRow {{ background:{bg}; border:2px solid {fg};"
            f"  border-left:4px solid {fg}; border-radius:6px; }}"
        )
        QTimer.singleShot(600, lambda: row.setStyleSheet(orig))

    def _rebuild_name_index(self):
        self._name_to_index = {}
        for i in range(self.varLayout.count()):
            item = self.varLayout.itemAt(i)
            if item and item.widget():
                name = item.widget()._fields[0].text().strip()
                if name:
                    self._name_to_index[name] = i

    def _refreshHighlighter(self):
        self._rebuild_name_index()
        variables = self._readVariableRows()
        self.editor.set_variables(variables, self._name_to_index)
        self._rebuildTokenBar(variables)

    def _rebuildTokenBar(self, variables):
        while self.tokenBarLayout.count():
            item = self.tokenBarLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for name in variables:
            idx = self._name_to_index.get(name, 0)
            bg, fg, border = palette_for(idx)
            chip = QPushButton(name)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setFixedHeight(22)
            chip.setStyleSheet(
                f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {border};"
                f"  border-radius:10px; padding:0 10px; font-size:11px; font-family:{FONT_MONO}; font-weight:700; }}"
                f"QPushButton:hover {{ background:{border}; color:#fff; }}"
            )
            chip.clicked.connect(lambda checked=False, n=name: self._insertAtCursor(f"{{{n}}}"))
            self.tokenBarLayout.addWidget(chip)
        self.tokenBarLayout.addStretch()

    # ── Subtask management ────────────────────────────────────
    def addSubtask(self):
        self.saveCurrent()
        self.subtasks.append({"template": "", "tests": 10, "variables": {}, "constraints": ""})
        self.subtaskList.addItem(f"Subtask {len(self.subtasks)}")
        self.subtaskList.setCurrentRow(len(self.subtasks) - 1)

    def removeSubtask(self):
        idx = self.subtaskList.currentRow()
        if idx < 0 or len(self.subtasks) <= 1:
            return
        self.subtasks.pop(idx)
        self.subtaskList.takeItem(idx)
        for i in range(self.subtaskList.count()):
            self.subtaskList.item(i).setText(f"Subtask {i + 1}")
        self.current_index = -1
        self.subtaskList.setCurrentRow(min(idx, len(self.subtasks) - 1))

    def switchSubtask(self, index):
        if index < 0:
            return
        self.saveCurrent()
        self.current_index = index
        data = self.subtasks[index]
        self.editor.setPlainText(data["template"])
        self.testCountInput.setValue(data["tests"])
        self._loadVariableRows(data["variables"])
        self._refreshHighlighter()
        self.constraintEditor.blockSignals(True)
        self.constraintEditor.setPlainText(data.get("constraints", ""))
        self.constraintEditor.blockSignals(False)

    def saveCurrent(self):
        if self.current_index == -1:
            return
        self.subtasks[self.current_index]["template"]    = self.editor.toPlainText()
        self.subtasks[self.current_index]["variables"]   = self._readVariableRows()
        self.subtasks[self.current_index]["constraints"] = self.constraintEditor.toPlainText()
        try:
            save("gen_subtasks", json.dumps(self.subtasks))
        except Exception:
            pass

    def saveTestCount(self, value):
        if self.current_index >= 0:
            self.subtasks[self.current_index]["tests"] = value
            try:
                save("gen_subtasks", json.dumps(self.subtasks))
            except Exception:
                pass

    def _onConstraintChanged(self):
        if self.current_index >= 0:
            self.subtasks[self.current_index]["constraints"] = self.constraintEditor.toPlainText()

    # ── Variable rows ─────────────────────────────────────────
    def _makeVarRow(self, varname="", vartype="int", lower="1", upper="100", charset=""):
        row = QWidget()
        row.setObjectName("varRow")
        row.setStyleSheet(
            f"QWidget#varRow {{ background:{BG2}; border:1px solid {BORDER};"
            f"  border-left:3px solid {ACCENT_DIM}; border-radius:6px; }}"
        )
        row.setFixedHeight(50)

        TYPE_COLORS = {
            "int":    ("#0d2540", "#1e6a9e", "#5bc8f5"),
            "float":  ("#152510", "#3a6a1e", "#7ed45a"),
            "string": ("#200d40", "#6a1e9e", "#c85bf5"),
        }

        hl = QHBoxLayout()
        hl.setContentsMargins(8, 5, 8, 5)
        hl.setSpacing(6)

        nameEdit = QLineEdit(varname)
        nameEdit.setPlaceholderText("name")
        nameEdit.setFixedWidth(72)
        nameEdit.setStyleSheet(
            f"QLineEdit {{ background:{BG1}; border:1px solid {BORDER_BRIGHT};"
            f"  border-radius:4px; color:#e8f4ff;"
            f"  font-family:{FONT_MONO}; font-size:13px; font-weight:700; padding:2px 6px; }}"
            f"QLineEdit:focus {{ border-color:{ACCENT}; }}"
        )

        typeBox = QComboBox()
        typeBox.addItems(["int", "float", "string"])
        typeBox.setCurrentText(vartype)
        typeBox.setFixedWidth(65)

        def styleTypeBox(t):
            bg, bd, fg = TYPE_COLORS.get(t, TYPE_COLORS["int"])
            typeBox.setStyleSheet(
                f"QComboBox {{ background:{bg}; border:1px solid {bd}; border-radius:10px;"
                f"  color:{fg}; font-size:11px; font-weight:700; padding:2px 6px 2px 8px; }}"
                f"QComboBox::drop-down {{ border:none; width:14px; }}"
                f"QComboBox QAbstractItemView {{ background:{BG2}; color:{TEXT_MAIN}; border:1px solid {BORDER}; selection-background-color:{ACCENT_DIM}; }}"
            )
        styleTypeBox(vartype)
        typeBox.currentTextChanged.connect(styleTypeBox)

        fstyle = (
            f"QLineEdit {{ background:{BG1}; border:1px solid {BORDER};"
            f"  border-radius:4px; color:{TEXT_MAIN}; font-size:12px; padding:2px 4px; }}"
            f"QLineEdit:focus {{ border-color:{ACCENT}; }}"
        )
        rangeSep = QLabel("→")
        rangeSep.setStyleSheet(f"color:{TEXT_HINT}; font-size:10px; background:transparent;")
        rangeSep.setFixedWidth(14)

        lowerEdit = QLineEdit(lower)
        lowerEdit.setPlaceholderText("min")
        lowerEdit.setFixedWidth(42)
        lowerEdit.setStyleSheet(fstyle)

        upperEdit = QLineEdit(upper)
        upperEdit.setPlaceholderText("max")
        upperEdit.setFixedWidth(42)
        upperEdit.setStyleSheet(fstyle)

        charsetEdit = QLineEdit(charset)
        charsetEdit.setPlaceholderText("abc…")
        charsetEdit.setFixedWidth(60)
        charsetEdit.setStyleSheet(fstyle)

        charsetLabel = QLabel("chars:")
        charsetLabel.setStyleSheet(f"color:{TEXT_HINT}; font-size:9px; background:transparent;")
        charsetWrap = QWidget()
        charsetWrap.setStyleSheet("background:transparent;")
        cwl = QHBoxLayout()
        cwl.setContentsMargins(0, 0, 0, 0)
        cwl.setSpacing(3)
        cwl.addWidget(charsetLabel)
        cwl.addWidget(charsetEdit)
        charsetWrap.setLayout(cwl)

        def updateCharset(t):
            charsetWrap.setVisible(t == "string")
        typeBox.currentTextChanged.connect(updateCharset)
        updateCharset(vartype)

        insertBtn = QPushButton("← insert")
        insertBtn.setFixedHeight(22)
        insertBtn.setStyleSheet(
            f"QPushButton {{ background:{BG1}; color:{TEXT_DIM}; border:1px solid {BORDER};"
            f"  border-radius:10px; padding:0 8px; font-size:10px; font-family:{FONT_MONO}; }}"
            f"QPushButton:hover {{ border-color:{ACCENT}; color:{ACCENT}; }}"
        )
        insertBtn.clicked.connect(lambda: self._insertAtCursor(f"{{{nameEdit.text().strip()}}}"))

        removeBtn = QPushButton("✕")
        removeBtn.setFixedSize(20, 20)
        removeBtn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{TEXT_HINT}; border:none; font-size:11px; }}"
            f"QPushButton:hover {{ color:{RED}; }}"
        )
        removeBtn.clicked.connect(lambda: self._removeVarRow(row))

        hl.addWidget(nameEdit)
        hl.addWidget(typeBox)
        hl.addWidget(lowerEdit)
        hl.addWidget(rangeSep)
        hl.addWidget(upperEdit)
        hl.addWidget(charsetWrap)
        hl.addStretch()
        hl.addWidget(insertBtn)
        hl.addWidget(removeBtn)
        row.setLayout(hl)
        row._fields = (nameEdit, typeBox, lowerEdit, upperEdit, charsetEdit)
        nameEdit.textChanged.connect(self._onVarChanged)
        return row

    def _applyRowAccentColors(self):
        for i in range(self.varLayout.count()):
            item = self.varLayout.itemAt(i)
            if not item or not item.widget():
                continue
            _, fg, _ = palette_for(i)
            item.widget().setStyleSheet(
                f"QWidget#varRow {{ background:{BG2}; border:1px solid {BORDER};"
                f"  border-left:3px solid {fg}; border-radius:6px; }}"
            )

    def _onVarChanged(self):
        self._applyRowAccentColors()
        self._refreshHighlighter()

    def addVariableRow(self):
        row = self._makeVarRow()
        self.varLayout.addWidget(row)
        self._applyRowAccentColors()
        self._refreshHighlighter()

    def _removeVarRow(self, row):
        self.varLayout.removeWidget(row)
        row.deleteLater()
        QTimer.singleShot(0, lambda: (self._applyRowAccentColors(), self._refreshHighlighter()))

    def _readVariableRows(self):
        variables = {}
        for i in range(self.varLayout.count()):
            item = self.varLayout.itemAt(i)
            if item and item.widget():
                row = item.widget()
                nameEdit, typeBox, lowerEdit, upperEdit, charsetEdit = row._fields
                name = nameEdit.text().strip()
                if not name:
                    continue
                vtype = typeBox.currentText()
                try:
                    lo = int(lowerEdit.text())
                except ValueError:
                    lo = 0
                try:
                    hi = int(upperEdit.text())
                except ValueError:
                    hi = 10
                entry = {"varname": name, "vartype": vtype, "lower": lo, "upper": hi}
                if vtype == "string":
                    entry["charset"] = charsetEdit.text() or "abc"
                variables[name] = entry
        return variables

    def _loadVariableRows(self, variables):
        while self.varLayout.count():
            item = self.varLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for name, v in variables.items():
            row = self._makeVarRow(
                varname=name,
                vartype=v.get("vartype", "int"),
                lower=str(v.get("lower", 1)),
                upper=str(v.get("upper", 100)),
                charset=v.get("charset", ""),
            )
            self.varLayout.addWidget(row)
        self._applyRowAccentColors()

    # ── Loop insertion ────────────────────────────────────────
    def insertLoop(self):
        var_names = list(self._readVariableRows().keys())
        dlg = LoopDialog(self, var_names)
        if dlg.exec() == QDialog.Accepted and dlg.result_value:
            self._insertAtCursor(f"@{dlg.result_value}{{  }}")

    # ── Template parser ───────────────────────────────────────
    def parse(self, text, variables):
        i = 0
        result = []
        while i < len(text):
            if text[i] == "{":
                j = text.find("}", i)
                if j == -1:
                    break
                name = text[i+1:j]
                result.append(variables.get(name, {"varname": "", "content": f"{{{name}}}"}))
                i = j + 1
            elif text[i] == "@":
                m = re.match(r'@([\w]+)\{', text[i:])
                if m:
                    count_str  = m.group(1)
                    body_start = i + m.end()
                    depth = 1
                    j = body_start
                    while j < len(text) and depth > 0:
                        if text[j] == "{":
                            k = text.find("}", j + 1)
                            if k != -1 and re.match(r'\w+$', text[j+1:k]):
                                j = k + 1
                                continue
                            depth += 1
                        elif text[j] == "}":
                            depth -= 1
                        j += 1
                    inner = text[body_start:j - 1]
                    parsed_inner = self.parse(inner, variables)
                    count = int(count_str) if count_str.isdigit() else count_str
                    result.append([count] + parsed_inner)
                    i = j
                else:
                    result.append({"varname": "", "content": text[i]})
                    i += 1
            elif text.startswith("[LOOP:", i):
                j = text.find("]", i)
                if j == -1:
                    break
                count = text[i+6:j]
                k = text.find("[/LOOP]", j)
                if k == -1:
                    break
                inner = text[j+1:k]
                parsed_inner = self.parse(inner, variables)
                result.append([int(count) if count.isdigit() else count] + parsed_inner)
                i = k + 7
            else:
                result.append({"varname": "", "content": text[i]})
                i += 1
        return result

    # ── Actions ───────────────────────────────────────────────
    def generateJson(self):
        self.saveCurrent()
        result = []
        for i, sub in enumerate(self.subtasks, 1):
            parsed = self.parse(sub["template"], sub["variables"])
            entry  = {"task": i, "tests": sub["tests"], "blueprint": parsed}
            if sub.get("constraints", "").strip():
                entry["constraints"] = sub["constraints"].strip()
            result.append(entry)
        self.output.setText(json.dumps(result, indent=4))

    def previewTest(self):
        self.saveCurrent()
        try:
            if self.current_index < 0:
                self.previewBox.setText("No subtask selected.")
                return
            sub       = self.subtasks[self.current_index]
            blueprint = self.parse(sub["template"], sub["variables"])
            self.previewBox.setText(testUtils.generateTestFromJson(blueprint, {}))
        except Exception as e:
            self.previewBox.setText(str(e))

    def saveJson(self):
        self.generateJson()
        file, _ = QFileDialog.getSaveFileName(self, "Save JSON", "", "*.json")
        if file:
            with open(file, "w", encoding="utf-8") as f:
                f.write(self.output.toPlainText())

    def loadJson(self):
        file, _ = QFileDialog.getOpenFileName(self, "Load JSON", "", "*.json")
        if not file:
            return
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.subtasks.clear()
        self.subtaskList.clear()
        for task in data:
            self.subtasks.append({
                "template":    "",
                "tests":       task.get("tests", 10),
                "variables":   {},
                "constraints": task.get("constraints", ""),
            })
            self.subtaskList.addItem(f"Subtask {task.get('task', '?')}")
        self.current_index = -1
        self.subtaskList.setCurrentRow(0)
        self.output.setText(json.dumps(data, indent=4))

    def sendToJudge(self):
        self.generateJson()
        self.parent_app.judgeTab.jsonEditor.setText(self.output.toPlainText())
        self.parent_app.tabs.setCurrentIndex(0)

    def _clearMemory(self):
        save("gen_subtasks", "")
        self.subtasks      = []
        self.current_index = -1
        self._name_to_index = {}
        self.subtaskList.clear()
        self.addSubtask()