# highlighters.py — Syntax highlighters for template and code editors

import re

from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt

from theme import ACCENT, palette_for


# ── Template highlighter ──────────────────────────────────────
class TemplateHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._var_formats: dict[str, QTextCharFormat] = {}
        self._loop_fmt    = self._make_fmt("#1e4a28", "#5bf59a", bold=True)
        self._unknown_fmt = self._make_fmt("#2a1a0a", "#c07040")

    @staticmethod
    def _make_fmt(bg, fg, bold=False, italic=False):
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(bg))
        fmt.setForeground(QColor(fg))
        fmt.setFontFamilies(["JetBrains Mono", "Fira Code", "Consolas"])
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def set_variables(self, variables: dict, name_to_index: dict):
        self._var_formats = {}
        for name in variables:
            idx = name_to_index.get(name, 0)
            bg, fg, _ = palette_for(idx)
            self._var_formats[name] = self._make_fmt(bg, fg, bold=True)
        self.rehighlight()

    def highlightBlock(self, text: str):
        for name, fmt in self._var_formats.items():
            token = "{" + name + "}"
            start = 0
            while True:
                idx = text.find(token, start)
                if idx == -1:
                    break
                self.setFormat(idx, len(token), fmt)
                start = idx + len(token)

        for m in re.finditer(r'\{(\w+)\}', text):
            if m.group(1) not in self._var_formats:
                self.setFormat(m.start(), m.end() - m.start(), self._unknown_fmt)

        for m in re.finditer(r'@[\w]+\{', text):
            self.setFormat(m.start(), m.end() - m.start(), self._loop_fmt)

        for m in re.finditer(r'(?<!\w)\}', text):
            self.setFormat(m.start(), 1, self._loop_fmt)


# ── Code highlighter ──────────────────────────────────────────
class CodeHighlighter(QSyntaxHighlighter):
    """Minimal but readable syntax highlighter for Python, C++, Java."""

    PYTHON_KEYWORDS = (
        "False None True and as assert async await break class continue def del "
        "elif else except finally for from global if import in is lambda nonlocal "
        "not or pass raise return try while with yield"
    ).split()

    CPP_KEYWORDS = (
        "alignas alignof auto bool break case catch char class const constexpr "
        "continue default delete do double else enum explicit extern false float "
        "for friend goto if inline int long namespace new noexcept nullptr operator "
        "private protected public register return short signed sizeof static "
        "static_assert struct switch template this throw true try typedef typeid "
        "typename union unsigned using virtual void volatile while"
    ).split()

    JAVA_KEYWORDS = (
        "abstract assert boolean break byte case catch char class const continue "
        "default do double else enum extends final finally float for goto if "
        "implements import instanceof int interface long native new null package "
        "private protected public return short static strictfp super switch "
        "synchronized this throw throws transient true try var void volatile while"
    ).split()

    def __init__(self, document, lang="Python"):
        super().__init__(document)
        self._lang = lang
        self._rules = []
        self._build_rules()

    def set_lang(self, lang):
        self._lang = lang
        self._rules = []
        self._build_rules()
        self.rehighlight()

    @staticmethod
    def _fmt(fg, bold=False, italic=False):
        f = QTextCharFormat()
        f.setForeground(QColor(fg))
        if bold:   f.setFontWeight(QFont.Weight.Bold)
        if italic: f.setFontItalic(True)
        return f

    def _build_rules(self):
        add  = self._rules.append
        lang = self._lang

        kw_list = {
            "Python": CodeHighlighter.PYTHON_KEYWORDS,
            "C++":    CodeHighlighter.CPP_KEYWORDS,
            "Java":   CodeHighlighter.JAVA_KEYWORDS,
        }.get(lang, [])

        kw_fmt   = self._fmt("#569cd6", bold=True)
        num_fmt  = self._fmt("#b5cea8")
        str_fmt  = self._fmt("#ce9178")
        cmt_fmt  = self._fmt("#6a9955", italic=True)
        fn_fmt   = self._fmt("#dcdcaa")
        pp_fmt   = self._fmt("#c586c0")
        type_fmt = self._fmt("#4ec9b0")

        for kw in kw_list:
            add((re.compile(rf"\b{re.escape(kw)}\b"), kw_fmt))

        add((re.compile(r"\b\d+\.?\d*([eE][+-]?\d+)?[fFlLuU]*\b"), num_fmt))
        add((re.compile(r"\b0[xX][0-9a-fA-F]+\b"), num_fmt))
        add((re.compile(r'"[^"\n]*"'), str_fmt))
        add((re.compile(r"'[^'\n]*'"), str_fmt))
        add((re.compile(r"\b([A-Za-z_]\w*)(?=\s*\()"), fn_fmt))

        if lang == "Python":
            add((re.compile(r"@\w+"), pp_fmt))
            add((re.compile(r"\bself\b"), type_fmt))
            add((re.compile(
                r"\b(int|float|str|list|dict|set|tuple|bool|type|object|len|range|print|"
                r"input|enumerate|zip|map|filter|sorted|reversed|any|all|min|max|sum|abs|"
                r"open|isinstance|hasattr|getattr|setattr)\b"
            ), type_fmt))
            add((re.compile(r"#[^\n]*"), cmt_fmt))

        elif lang in ("C++", "Java"):
            add((re.compile(r"#\s*(include|define|pragma|ifdef|ifndef|endif|if|else)\b"), pp_fmt))
            add((re.compile(
                r"\b(std|cout|cin|endl|vector|string|map|set|pair|auto|int|long|"
                r"double|float|char|bool|void|nullptr)\b"
            ), type_fmt))
            add((re.compile(r"//[^\n]*"), cmt_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)

        if self._lang in ("C++", "Java"):
            self._highlight_ml_comments(text)

    def _highlight_ml_comments(self, text):
        cmt_fmt    = self._fmt("#6a9955", italic=True)
        start_expr = re.compile(r"/\*")
        end_expr   = re.compile(r"\*/")

        self.setCurrentBlockState(0)
        start_index = 0
        if self.previousBlockState() != 1:
            m = start_expr.search(text)
            start_index = m.start() if m else -1

        while start_index >= 0:
            m_end = end_expr.search(text, start_index)
            if m_end:
                length = m_end.end() - start_index
                self.setCurrentBlockState(0)
            else:
                self.setCurrentBlockState(1)
                length = len(text) - start_index
            self.setFormat(start_index, length, cmt_fmt)
            m_next = start_expr.search(text, start_index + length)
            start_index = m_next.start() if m_next else -1