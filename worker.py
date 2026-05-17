# worker.py — Background thread for running tests

from PySide6.QtCore import QThread, Signal
import testUtils


class TestWorker(QThread):
    finished   = Signal()
    progress   = Signal(int)
    new_result = Signal(object)   # emits the raw result dict from testUtils

    def __init__(
        self, user_code, answer_code, jsonData, timeLimit,
        user_lang, answer_lang, input_file, output_file
    ):
        super().__init__()
        self.user_code   = user_code
        self.answer_code = answer_code
        self.jsonData    = jsonData
        self.timeLimit   = timeLimit
        self.user_lang   = user_lang
        self.answer_lang = answer_lang
        self.input_file  = input_file
        self.output_file = output_file

    def run(self):
        import time as _time

        ext_map      = {"Python": ".py",     "C++": ".cpp",  "Java": ".java"}
        lang_str_map = {"Python": "python",  "C++": "cpp",   "Java": "java"}

        u_ext  = ext_map.get(self.user_lang,   ".py")
        a_ext  = ext_map.get(self.answer_lang, ".py")
        u_lang = lang_str_map.get(self.user_lang,   "python")
        a_lang = lang_str_map.get(self.answer_lang, "python")

        # Unique timestamp so mtime always changes → C++ recompiles every run
        ts    = int(_time.time() * 1000)
        u_src = f"temp_user_{ts}{u_ext}"
        a_src = f"temp_answer_{ts}{a_ext}"

        with open(u_src, "w", encoding="utf-8") as f:
            f.write(self.user_code)
        with open(a_src, "w", encoding="utf-8") as f:
            f.write(self.answer_code)

        testUtils._compile_cache.clear()   # never reuse stale binary

        for result in testUtils.runTest(
            u_src, a_src, u_lang,
            self.jsonData, self.timeLimit, self.output_file,
            answer_lang=a_lang,
        ):
            self.progress.emit(result["progress"])
            self.new_result.emit(result)

        self.finished.emit()