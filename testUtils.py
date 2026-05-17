import os
import random
import subprocess
import tempfile
import shutil

# ─────────────────────────────────────────────────────────────
#  Compilation cache  { source_path -> compiled_binary_path }
#  C++ files are only recompiled when their mtime changes.
# ─────────────────────────────────────────────────────────────
_compile_cache: dict[str, tuple[float, str]] = {}   # path -> (mtime, binary)


def _compile_cpp(source: str) -> str | None:
    """Compile a C++ file; return binary path or None on error."""
    mtime = os.path.getmtime(source)
    if source in _compile_cache:
        cached_mtime, binary = _compile_cache[source]
        if cached_mtime == mtime:
            return binary

    binary = source.replace(".cpp", "") + "_bin"
    result = subprocess.run(
        ["g++", "-O2", "-o", binary, source],
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if result.returncode != 0:
        print(f"[compile error] {source}:\n{result.stderr.decode()}")
        return None

    _compile_cache[source] = (mtime, binary)
    return binary


# ─────────────────────────────────────────────────────────────
#  Run one program against one input string
#
#  lang        : "python" | "cpp" | "java"
#  source      : path to source file
#  input_str   : the test input as a string
#  output_file : if set, the program is expected to write its output
#                to this file (file-based I/O mode); each call gets
#                a unique temp copy so user and answer don't collide.
#                Pass None for stdout mode.
#  time_limit  : seconds (float)
#
#  Returns a list of whitespace-split tokens, or ["TLE"] / ["RTE"]
# ─────────────────────────────────────────────────────────────
def _run_program(
    lang: str,
    source: str,
    input_str: str,
    output_file: str | None,
    time_limit: float,
) -> list[str]:
    lang = lang.lower()

    # Always write input.inp so file-based readers can open it
    with open("input.inp", "w", encoding="utf-8") as f:
        f.write(input_str)

    # Use a per-call temp output file to avoid user/answer collision
    if output_file:
        tmp_out = output_file + ".tmp"
    else:
        tmp_out = None

    try:
        if lang == "cpp":
            binary = _compile_cpp(source)
            if binary is None:
                return ["RTE"]
            cmd = [binary]

        elif lang == "python":
            cmd = ["python", source]

        elif lang == "java":
            class_dir  = os.path.dirname(os.path.abspath(source)) or "."
            class_name = os.path.splitext(os.path.basename(source))[0]
            mtime      = os.path.getmtime(source)
            class_file = os.path.join(class_dir, class_name + ".class")

            needs_compile = (
                not os.path.exists(class_file)
                or os.path.getmtime(class_file) < mtime
            )
            if needs_compile:
                r = subprocess.run(
                    ["javac", source],
                    stderr=subprocess.PIPE,
                    timeout=30,
                )
                if r.returncode != 0:
                    print(f"[compile error] {source}:\n{r.stderr.decode()}")
                    return ["RTE"]
            cmd = ["java", "-cp", class_dir, class_name]

        else:
            print(f"[error] Unknown language: {lang}")
            return ["RTE"]

        result = subprocess.run(
            cmd,
            input=input_str.encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=time_limit,
        )

        if result.returncode != 0:
            return ["RTE"]

        if tmp_out:
            # Program writes to a file; rename the expected output path to tmp
            # so both user and answer can run without overwriting each other.
            # The program itself still writes to `output_file` by name — we
            # copy that to tmp_out immediately after it finishes.
            if os.path.exists(output_file):
                shutil.copy2(output_file, tmp_out)
            if os.path.exists(tmp_out):
                with open(tmp_out, "r", encoding="utf-8") as f:
                    raw = f.read()
            else:
                raw = ""
        else:
            raw = result.stdout.decode(errors="replace")

        return raw.split() or ["(empty)"]

    except subprocess.TimeoutExpired:
        return ["TLE"]
    except FileNotFoundError as e:
        print(f"[error] Executable not found: {e}")
        return ["RTE"]
    except Exception as e:
        print(f"[error] Unexpected: {e}")
        return ["RTE"]


# ─────────────────────────────────────────────────────────────
#  Test input generator
# ─────────────────────────────────────────────────────────────
def generateTestFromJson(commands: list, variables: dict) -> str:
    output = ""

    for cmd in commands:
        # Loop node: [count, ...inner_commands]
        if isinstance(cmd, list):
            count = cmd[0]
            if isinstance(count, str):
                count = variables[count]
            for _ in range(int(count)):
                output += generateTestFromJson(cmd[1:], variables)
            continue

        varname = cmd.get("varname", "")

        # Literal / whitespace token
        if varname == "":
            output += cmd.get("content", "")
            continue

        # Random value generation
        lower = cmd["lower"]
        upper = cmd["upper"]
        if isinstance(lower, str):
            lower = variables[lower]
        if isinstance(upper, str):
            upper = variables[upper]

        vartype = cmd.get("vartype", "int")
        if vartype == "int":
            value = random.randint(int(lower), int(upper))
        elif vartype == "float":
            value = random.uniform(float(lower), float(upper))
        else:  # string
            charset = cmd.get("charset", "abc")
            length = random.randint(int(lower), int(upper))
            value = "".join(random.choice(charset) for _ in range(length))

        variables[varname] = value
        output += str(value)

    return output


# ─────────────────────────────────────────────────────────────
#  Main test runner  (generator — yields one result per test)
#
#  user_source    : path to user's source file
#  answer_source  : path to reference/judge source file
#  user_lang      : "python" | "cpp" | "java"
#  answer_lang    : "python" | "cpp" | "java"  (defaults to user_lang)
#  test_blueprints: list of task dicts from JSON config
#  time_limit     : seconds per run
#  output_file    : if set, programs write here instead of stdout
#                   pass None (or omit) for stdout mode
# ─────────────────────────────────────────────────────────────
def runTest(
    user_source: str,
    answer_source: str,
    user_lang: str,
    test_blueprints: list,
    time_limit: float = 1.0,
    output_file: str | None = None,
    answer_lang: str | None = None,
):
    if answer_lang is None:
        answer_lang = user_lang

    total = sum(task.get("tests", 0) for task in test_blueprints)
    done = 0

    for task in test_blueprints:
        task_id  = task["task"]
        blueprint = task["blueprint"]
        num_tests = task["tests"]

        for _ in range(num_tests):
            # Generate input
            inp = generateTestFromJson(blueprint, {})

            # Run both programs with the same input via stdin
            user_out   = _run_program(user_lang,   user_source,   inp, output_file, time_limit)
            answer_out = _run_program(answer_lang, answer_source, inp, output_file, time_limit)

            # Verdict
            if user_out == ["RTE"]:
                verdict = "RTE"
            elif user_out == ["TLE"]:
                verdict = "TLE"
            elif answer_out in (["RTE"], ["TLE"]):
                # Judge itself crashed — mark as judge error, skip
                verdict = "JE"
            elif user_out == answer_out:
                verdict = "AC"
            else:
                verdict = "WA"

            done += 1

            yield {
                "task":     task_id,
                "index":    done,
                "input":    inp,
                "user":     user_out,
                "answer":   answer_out,
                "verdict":  verdict,
                "progress": int(done * 100 / total),
            }


# ─────────────────────────────────────────────────────────────
#  Convenience: write a test to a file and return the string
# ─────────────────────────────────────────────────────────────
def writeTest(blueprint: list, input_file: str) -> str:
    test_str = generateTestFromJson(blueprint, {})
    with open(input_file, "w", encoding="utf-8") as f:
        f.write(test_str)
    return test_str


# ─────────────────────────────────────────────────────────────
#  CLI smoke-test
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: testUtils.py <user.py> <answer.py> [time_limit]")
        sys.exit(1)

    user_src   = sys.argv[1]
    answer_src = sys.argv[2]
    tl         = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    # Minimal inline blueprint for quick smoke-test
    blueprints = [
        {
            "task": 1,
            "tests": 5,
            "blueprint": [
                {"varname": "n", "vartype": "int", "lower": 1, "upper": 10},
                {"varname": "", "content": "\n"},
            ],
        }
    ]

    correct = 0
    total   = 0
    for res in runTest(user_src, answer_src, "python", blueprints, tl):
        total += 1
        if res["verdict"] == "AC":
            correct += 1
        print(f"[{res['verdict']}] task={res['task']} test={res['index']}")

    print(f"\n{correct}/{total} passed")