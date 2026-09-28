import ast
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time


MAX_SECONDS = 3
MAX_MEMORY_MB = 128
MAX_OUTPUT_CHARS = 12_000
BLOCKED_PYTHON_NAMES = {
    "compile",
    "eval",
    "exec",
    "input",
    "open",
    "__import__",
}
BLOCKED_PYTHON_MODULES = {
    "ctypes",
    "http",
    "importlib",
    "json",
    "multiprocessing",
    "os",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "urllib",
}
BLOCKED_JAVASCRIPT_TOKENS = re.compile(
    r"\b(require|import|process|child_process|fs|net|http|https|dgram|"
    r"worker_threads|fetch|XMLHttpRequest|WebSocket|eval|Function|WebAssembly)\b",
    re.IGNORECASE,
)
BLOCKED_SQL_TOKENS = re.compile(
    r"\b(attach|detach|pragma|load_extension|readfile|writefile)\b",
    re.IGNORECASE,
)


def _result(success, stdout="", stderr="", started=None, timed_out=False):
    output = (stdout or "")[:MAX_OUTPUT_CHARS]
    error = (stderr or "")[:MAX_OUTPUT_CHARS]
    if len(stdout or "") > MAX_OUTPUT_CHARS:
        output += "\n[Output truncated.]"
    if len(stderr or "") > MAX_OUTPUT_CHARS:
        error += "\n[Error output truncated.]"
    return {
        "success": success,
        "stdout": output,
        "stderr": error,
        "duration_ms": round((time.perf_counter() - started) * 1000) if started else 0,
        "timed_out": timed_out,
        "sandbox": "guarded-local",
        "limits": {
            "timeout_seconds": MAX_SECONDS,
            "memory_mb": MAX_MEMORY_MB,
            "memory_limit_enforced": os.name == "nt",
            "output_characters": MAX_OUTPUT_CHARS,
            "network": "blocked by policy",
            "working_directory": "temporary",
        },
    }


def _python_policy(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as ex:
        return False, f"Line {ex.lineno}: {ex.msg}"

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "Python imports are disabled in the local sandbox."
        if isinstance(node, ast.Name) and node.id in BLOCKED_PYTHON_NAMES:
            return False, f"Python operation '{node.id}' is blocked in the local sandbox."
        if isinstance(node, ast.Attribute):
            root = node
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in BLOCKED_PYTHON_MODULES:
                return False, f"Python module '{root.id}' is blocked in the local sandbox."
    return True, ""


def _minimal_environment():
    environment = {
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PATH": os.environ.get("PATH", ""),
    }
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
        if os.environ.get(key):
            environment[key] = os.environ[key]
    return environment


def _current_memory_bytes(process):
    if os.name != "nt":
        return 0
    try:
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(ProcessMemoryCounters)
        get_memory = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        get_memory.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        get_memory.restype = wintypes.BOOL
        if get_memory(process._handle, ctypes.byref(counters), counters.cb):
            return int(counters.WorkingSetSize)
    except (AttributeError, OSError):
        pass
    return 0


def _run_process(command, code):
    started = time.perf_counter()
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    with tempfile.TemporaryDirectory(prefix="syntax-local-ai-") as workdir:
        try:
            process = subprocess.Popen(
                command,
                cwd=workdir,
                env=_minimal_environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        except OSError as ex:
            return _result(False, "", str(ex), started)

        output = {}

        def collect_output():
            output["value"] = process.communicate()

        collector = threading.Thread(target=collect_output, daemon=True)
        collector.start()
        timed_out = False
        memory_exceeded = False
        while collector.is_alive():
            if time.perf_counter() - started >= MAX_SECONDS:
                timed_out = True
                process.kill()
                break
            if _current_memory_bytes(process) > MAX_MEMORY_MB * 1024 * 1024:
                memory_exceeded = True
                process.kill()
                break
            time.sleep(0.05)
        collector.join(timeout=1)
        stdout, stderr = output.get("value", ("", ""))
        if timed_out:
            return _result(False, stdout, f"Execution stopped after {MAX_SECONDS} seconds.", started, True)
        if memory_exceeded:
            return _result(False, stdout, f"Execution stopped after exceeding the {MAX_MEMORY_MB} MB memory limit.", started)

        completed_returncode = process.returncode

    return _result(
        completed_returncode == 0,
        stdout,
        stderr,
        started,
    )


def _run_python(code):
    allowed, error = _python_policy(code)
    if not allowed:
        return _result(False, "", error, time.perf_counter())
    return _run_process([sys.executable, "-I", "-S", "-c", code], code)


def _run_javascript(code):
    if BLOCKED_JAVASCRIPT_TOKENS.search(code):
        return _result(
            False,
            "",
            "JavaScript imports, network, process, and filesystem APIs are blocked in the local sandbox.",
            time.perf_counter(),
        )
    node = shutil.which("node")
    if not node:
        return _result(False, "", "Node.js is not installed on this machine.", time.perf_counter())
    return _run_process([node, "--no-addons", "-e", code], code)


def _run_sql(code):
    started = time.perf_counter()
    if BLOCKED_SQL_TOKENS.search(code):
        return _result(False, "", "File attachment, pragmas, and SQLite extension APIs are blocked.", started)

    connection = sqlite3.connect(":memory:")
    connection.set_progress_handler(
        lambda: 1 if time.perf_counter() - started > MAX_SECONDS else 0,
        1_000,
    )
    cursor = connection.cursor()
    output = []
    try:
        statements = [part.strip() for part in code.split(";") if part.strip()]
        if len(statements) > 50:
            return _result(False, "", "SQL is limited to 50 statements.", started)
        for statement in statements:
            cursor.execute(statement)
            if cursor.description:
                output.append(" | ".join(column[0] for column in cursor.description))
                output.extend(
                    " | ".join(str(value) for value in row)
                    for row in cursor.fetchall()
                )
    except sqlite3.OperationalError as ex:
        if "interrupted" in str(ex).lower():
            return _result(False, "", "SQL stopped after the execution time limit.", started, True)
        return _result(False, "", str(ex), started)
    except sqlite3.Error as ex:
        return _result(False, "", str(ex), started)
    finally:
        connection.close()

    return _result(True, "\n".join(output) or "SQL completed without rows.", "", started)


def run_sandboxed_code(language, code):
    language = language.strip().lower()
    if language in ("auto", "py", "python"):
        return _run_python(code)
    if language in ("js", "javascript", "node"):
        return _run_javascript(code)
    if language == "sql":
        return _run_sql(code)
    return _result(
        False,
        "",
        "Sandbox execution supports Python, JavaScript, and in-memory SQL.",
        time.perf_counter(),
    )
