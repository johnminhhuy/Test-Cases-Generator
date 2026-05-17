# ai_worker.py — AI-powered code analysis with multiple providers

import json
import urllib.request
import urllib.error
import requests

from PySide6.QtCore import QThread, Signal
from widgets import load, save

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_ANALYSIS = """You are an expert competitive programming judge assistant.

A solution has failed a test case. Tell the user EXACTLY what is wrong.

You have:
- The problem statement (if provided)
- The user's code (failed)
- The reference/answer code (always correct)
- The exact input, expected output, and actual output

Structure your response as:

**What went wrong:**
<1-3 sentences — the logical error, not just "output differs">

**Why this input exposes it:**
<why this specific input triggers the bug>

**The fix:**
<only the corrected lines, not the whole program>

You have the reference code. Be precise and direct. Do not hedge."""

SYSTEM_ANSWER = """You are an expert competitive programmer.
Write a correct, efficient reference solution for the given problem.
Return ONLY the source code. No explanation, no markdown fences."""

SYSTEM_JSON = """You are a competitive programming test-case generator expert.
Generate a test blueprint JSON for the given problem.

RULES — every entry in "blueprint" must be exactly ONE of:

1. Variable generator:
   {"varname": "n", "vartype": "int", "lower": 1, "upper": 100}

2. Literal content:
   {"varname": "", "content": "\\n"}   or   {"varname": "", "content": " "}

3. Loop list (first element = count variable or integer):
   ["n", {"varname": "x", "vartype": "int", "lower": 1, "upper": 100}, {"varname": "", "content": " "}]

Supported vartypes: "int", "float", "string"
For string: add "lower" (min length), "upper" (max length), "charset" (allowed chars)
"lower" and "upper" may reference previously defined variable names as strings.

NEVER use raw strings. NEVER add explanations. NEVER wrap in markdown fences.
Return ONLY valid JSON in this format:
[{"task": 1, "tests": 50, "blueprint": [...]}]"""


class AIWorker(QThread):
    chunk    = Signal(str)
    finished = Signal()
    error    = Signal(str)

    def __init__(self, user_code, answer_code, test_input,
                 expected, got, verdict, task, index,
                 language="C++", problem_statement="", output_mode="analysis"):
        super().__init__()
        self.user_code         = user_code
        self.answer_code       = answer_code
        self.test_input        = test_input
        self.expected          = expected
        self.got               = got
        self.verdict           = verdict
        self.task              = task
        self.index             = index
        self.language          = language
        self.problem_statement = problem_statement
        self.output_mode       = output_mode

    def _build_prompt(self):
        stmt = self.problem_statement.strip() or \
               "(No problem statement — analyse from code and I/O only)"

        if self.output_mode == "analysis":
            return f"""Task {self.task}, Test {self.index} — Verdict: {self.verdict}
Language: {self.language}

━━━ PROBLEM STATEMENT ━━━
{stmt}

━━━ USER CODE (failed) ━━━
```{self.language.lower()}
{self.user_code}
```

━━━ REFERENCE CODE (correct) ━━━
```{self.language.lower()}
{self.answer_code}
```

━━━ FAILING TEST ━━━
Input:
{self.test_input}

Expected output:
{self.expected}

User's output:
{self.got}

Analyse exactly why the user's code produces the wrong output on this input.
Use the reference code to understand what the correct logic should be."""

        elif self.output_mode == "answer":
            hints = {
                "C++":    "Use C++17. #include <bits/stdc++.h>. ios_base::sync_with_stdio(0); cin.tie(0);",
                "Python": "Python 3. import sys; input = sys.stdin.readline",
                "Java":   "Java with BufferedReader for fast input.",
            }
            return f"""{hints.get(self.language, '')}

PROBLEM:
{stmt}"""

        elif self.output_mode == "json":
            return f"""
Generate a test blueprint JSON for this competitive programming problem.

IMPORTANT:
This is NOT normal testcase JSON.

The blueprint is a procedural generation language interpreted by Python code.

━━━━━━━━━━ VALID COMMAND TYPES ━━━━━━━━━━

Every entry inside "blueprint" MUST be exactly ONE of:

1. A variable generator object
2. A literal content object
3. A loop list

DO NOT generate anything else.

━━━━━━━━━━ 1. VARIABLE GENERATOR OBJECT ━━━━━━━━━━

Example:

{{
    "varname": "n",
    "vartype": "int",
    "lower": 1,
    "upper": 100
}}

Supported vartype values: "int", "float", "string"

String example:

{{
    "varname": "s",
    "vartype": "string",
    "lower": 3,
    "upper": 10,
    "charset": "abcde"
}}

━━━━━━━━━━ 2. LITERAL CONTENT OBJECT ━━━━━━━━━━

{{
    "varname": "",
    "content": " "
}}

or

{{
    "varname": "",
    "content": "\\n"
}}

Raw strings are NOT allowed. ALWAYS wrap literal text.

━━━━━━━━━━ 3. LOOP LIST ━━━━━━━━━━

[
    "n",
    {{
        "varname": "x",
        "vartype": "int",
        "lower": 1,
        "upper": 100
    }},
    {{
        "varname": "",
        "content": " "
    }}
]

The first element is the loop count (integer or variable name).

━━━━━━━━━━ FULL VALID EXAMPLE ━━━━━━━━━━

[
    {{
        "task": 1,
        "tests": 5,
        "blueprint": [
            {{
                "varname": "n",
                "vartype": "int",
                "lower": 1,
                "upper": 10
            }},
            {{
                "varname": "",
                "content": "\\n"
            }},
            [
                "n",
                {{
                    "varname": "x",
                    "vartype": "int",
                    "lower": 1,
                    "upper": 100
                }},
                {{
                    "varname": "",
                    "content": " "
                }}
            ],
            {{
                "varname": "",
                "content": "\\n"
            }}
        ]
    }}
]

━━━━━━━━━━ IMPORTANT RULES ━━━━━━━━━━

- Generate ONLY valid JSON
- Do NOT include explanations
- Do NOT include markdown
- Do NOT wrap the response in ```json

━━━━━━━━━━ PROBLEM ━━━━━━━━━━

{self.problem_statement}
"""

        return stmt   # fallback

    def _system_prompt(self):
        return {
            "analysis": SYSTEM_ANALYSIS,
            "answer":   SYSTEM_ANSWER,
            "json":     SYSTEM_JSON,
        }.get(self.output_mode, SYSTEM_ANALYSIS)

    def run(self):
        mode = load("ai_mode", "basic")

        try:
            if mode == "basic (no setup)":
                response = self._basic_analysis()
                self.chunk.emit(response)
                self.finished.emit()
            elif mode == "groq (free API)":
                self._call_groq_streaming()
            elif mode == "custom API":
                response = self._call_custom_api()
                self.chunk.emit(response)
                self.finished.emit()
            else:
                response = self._basic_analysis()
                self.chunk.emit(response)
                self.finished.emit()
        except Exception as e:
            self.error.emit(f"AI Error: {str(e)}")

    def _basic_analysis(self):
        """Simple pattern-based analysis without external API"""
        analysis = []
        analysis.append(f"## Analysis for Task {self.task}, Test {self.index} ({self.verdict}) - {self.language}\n")

        if self.problem_statement:
            analysis.append(f"### Problem: {self.problem_statement}\n\n")

        issues = []

        if self.language == "Python":
            if "/" in self.user_code and "//" not in self.user_code:
                issues.append("⚠️ Possible integer division: Use // for integer division in Python")
            if "def " in self.user_code and "return" not in self.user_code:
                issues.append("⚠️ Function may be missing return statement")
            if "input()" in self.user_code and "split()" not in self.user_code:
                issues.append("⚠️ Input may not be split correctly: Use input().split()")

        elif self.language == "C++":
            if ("int " in self.user_code or "void " in self.user_code) and "return" not in self.user_code:
                issues.append("⚠️ Function may be missing return statement")
            if "cin" in self.user_code and ">>" not in self.user_code:
                issues.append("⚠️ Input reading may be incorrect: Use cin >> var")
            if "cout" in self.user_code and "endl" not in self.user_code and "\\n" not in self.user_code:
                issues.append("⚠️ Output may be missing newlines: Use cout << ... << endl or \\n")

        elif self.language == "Java":
            if "/" in self.user_code and "//" not in self.user_code:
                issues.append("⚠️ Possible integer division: Use / for floating point or cast to double")
            if ("public " in self.user_code or "private " in self.user_code) and "return" not in self.user_code:
                issues.append("⚠️ Function may be missing return statement")
            if "Scanner" in self.user_code and "next" not in self.user_code:
                issues.append("⚠️ Input reading may be incorrect: Use scanner.next() or scanner.nextLine()")
            if "System.out.print" in self.user_code and "println" not in self.user_code:
                issues.append("⚠️ Output may be missing newlines: Use System.out.println()")

        if "for" in self.user_code and ("<" in self.user_code or ">" in self.user_code):
            issues.append("⚠️ Possible off-by-one error: Check loop bounds")

        expected_lines = self.expected.strip().split('\n')
        got_lines = self.got.strip().split('\n')
        if len(expected_lines) != len(got_lines):
            issues.append(f"⚠️ Line count mismatch: Expected {len(expected_lines)} lines, got {len(got_lines)} lines")

        if self.expected.strip() != self.got.strip():
            if self.expected.replace(' ', '') == self.got.replace(' ', ''):
                issues.append("⚠️ Whitespace mismatch: Check for extra/missing spaces")

        try:
            expected_val = float(self.expected.strip())
            got_val = float(self.got.strip())
            if abs(expected_val - got_val) > 0.001:
                ratio = got_val / expected_val if expected_val != 0 else 0
                if abs(ratio - 2) < 0.1:
                    issues.append(f"⚠️ Output is ~2x expected. Check for multiplication by 2 error")
                elif abs(ratio - 0.5) < 0.1:
                    issues.append(f"⚠️ Output is ~0.5x expected. Check for division by 2 error")
        except:
            pass

        if issues:
            analysis.append("### Potential Issues Found:\n")
            for issue in issues:
                analysis.append(f"- {issue}\n")
        else:
            analysis.append("### No obvious pattern issues found.\n")
            analysis.append("### Suggestions:\n")
            analysis.append("- Compare your logic with the reference code\n")
            analysis.append("- Check edge cases (empty input, single element, etc.)\n")

        analysis.append("\n### For better analysis, switch to Groq mode:\n")
        analysis.append("1. Click ⚙️ Settings in the main window\n")
        analysis.append("2. Select 'groq (free API)'\n")

        return ''.join(analysis)

    def _call_groq_streaming(self):
        """Call Groq API with streaming support"""
        api_key = load("groq_key", "").strip()
        if not api_key:
            self.error.emit("NO_KEY: Please configure your Groq API key in AI settings (click ⚙️ Settings)")
            return

        model = load("groq_model", GROQ_MODEL)

        prompt = self._build_prompt()
        if not prompt or not prompt.strip():
            self.error.emit("EMPTY_PROMPT: Problem statement is empty")
            return

        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user",   "content": prompt},
        ]

        try:
            response = requests.post(GROQ_URL, json={
                "model": model,
                "messages": messages,
                "stream": True,
            }, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }, stream=True, timeout=60)

            if response.status_code == 401:
                self.error.emit("BAD_KEY: Invalid API key")
                return
            elif response.status_code == 403:
                self.error.emit(f"FORBIDDEN: {response.text}\n\nTry using model 'llama-3.3-70b-versatile'")
                return
            elif response.status_code != 200:
                self.error.emit(f"Groq API error ({response.status_code}): {response.text}")
                return

            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    token = obj["choices"][0]["delta"].get("content", "")
                    if token:
                        self.chunk.emit(token)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
            self.finished.emit()

        except requests.exceptions.RequestException as e:
            self.error.emit(f"Network error: {str(e)}\n\nCheck your internet connection.")
        except Exception as e:
            self.error.emit(str(e))

    def _call_custom_api(self):
        """Call custom API"""
        api_url = load("custom_api_url", "")
        api_key = load("custom_api_key", "")

        if not api_url:
            raise Exception("Custom API URL not configured")

        headers = {"content-type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        prompt = self._build_prompt()

        try:
            response = requests.post(api_url, json={
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000
            }, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            response = requests.post(api_url, json={
                "prompt": prompt,
                "max_tokens": 1000
            }, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get("response", data.get("text", str(data)))